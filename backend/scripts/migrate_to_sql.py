import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup paths
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from apps.database.connection import init_db, get_session
from apps.database.models import (
    DeadStream, AutomationProfile, AutomationPeriod,
    ChannelRegexConfig, ChannelRegexPattern, SystemSetting
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', str(backend_dir / 'data')))

# All JSON files that may be migrated, used for backup and re-run prevention
ALL_MIGRATION_FILES = [
    'dead_streams.json',
    'automation_config.json',
    'channel_regex_config.json',
    'changelog.json',
    'stream_checker_config.json',
    'auto_create_rules.json',
    'scheduling_config.json',
    'dispatcharr_config.json',
    'session_settings.json',
]


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return None


def parse_datetime(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except Exception:
        logger.warning(f"Could not parse datetime value: {iso_str!r}")
        return None


def migrate_dead_streams(session, data_dir) -> int:
    data = load_json(data_dir / 'dead_streams.json')
    if not data:
        return 0
    count = 0
    for url, item in data.items():
        dead = DeadStream(
            url=url,
            stream_id=item.get('stream_id'),
            stream_name=item.get('stream_name'),
            channel_id=item.get('channel_id'),
            marked_dead_at=parse_datetime(item.get('marked_dead_at')),
            reason=item.get('reason', 'unknown')
        )
        session.merge(dead)
        count += 1
    logger.info(f"✓ Migrated {count} Dead Streams from {data_dir.name}")
    return count


def _build_cron(schedule: dict, per_item: dict) -> str:
    """
    Reconstruct a cron schedule string from the legacy JSON period structure.

    The old format stores schedule as:
        {"type": "interval", "value": 20}           # run every 20 minutes
        {"type": "cron",     "value": "0 * * * *"}  # explicit cron expression
        {"type": "interval", "value": "*/15 * * * *"}  # already a cron string

    If the value is already a fully-formed cron expression we use it verbatim.
    Bare integers are treated as minute-intervals (*/N * * * *).
    Anything unrecognised is stored as-is so no data is silently dropped.
    """
    sched_type = schedule.get('type', '')
    value = schedule.get('value', '')

    if not value and not sched_type:
        # Fall back to top-level cron_schedule field if present
        return per_item.get('cron_schedule', '0 * * * *')

    value_str = str(value).strip()

    # Already a proper cron expression (contains spaces -> 5 fields)
    if ' ' in value_str:
        return value_str

    if sched_type == 'interval':
        try:
            minutes = int(value_str)
            return f'*/{minutes} * * * *'
        except (ValueError, TypeError):
            # value_str was not a plain integer; return as-is
            return value_str

    if sched_type == 'cron':
        return value_str

    # Unknown type -- preserve value so nothing is lost
    logger.warning(f"Unknown schedule type {sched_type!r}; storing value verbatim: {value_str!r}")
    return value_str


def migrate_automation(session, data_dir) -> int:
    data = load_json(data_dir / 'automation_config.json')
    if not data:
        return 0

    rows_written = 0

    # --- Global automation settings ---
    # These three keys live at the top level of automation_config.json and must
    # be written to SystemSetting individually (matching how AutomationConfigManager reads them).
    global_keys = (
        'regular_automation_enabled',
        'playlist_update_interval_minutes',
        'validate_existing_streams',
    )
    for key in global_keys:
        if key in data:
            setting = SystemSetting(key=key, value=data[key])
            session.merge(setting)
            rows_written += 1
            logger.info(f"  ✓ Migrated global automation setting: {key}")

    # --- Profiles ---
    # Build a json_id -> new DB id map so periods can resolve their profile FK correctly.
    json_id_to_db_id: dict = {}
    count_profiles = 0

    profiles = data.get('profiles', {})
    for p_id, p_item in profiles.items():
        name = p_item.get('name', 'Profile')

        existing = session.query(AutomationProfile).filter(AutomationProfile.name == name).first()
        if existing:
            logger.info(f"  Automation Profile '{name}' already exists in DB, skipping.")
            json_id_to_db_id[str(p_id)] = existing.id
            continue

        extra = {
            'stream_matching': p_item.get('stream_matching'),
            'stream_checking': p_item.get('stream_checking'),
            'scoring_weights': p_item.get('scoring_weights'),
        }
        prof = AutomationProfile(
            name=name,
            description=p_item.get('description'),
            enabled=p_item.get('enabled', True),
            parallel_checks=p_item.get('parallel_checks', 1),
            extra_settings=extra,
        )
        session.add(prof)
        session.flush()  # populate prof.id
        json_id_to_db_id[str(p_id)] = prof.id
        count_profiles += 1
        rows_written += 1

    # --- Periods ---
    count_periods = 0

    periods = data.get('automation_periods', {})
    for per_id, per_item in periods.items():
        name = per_item.get('name', 'Period')

        existing_period = session.query(AutomationPeriod).filter(AutomationPeriod.name == name).first()
        if existing_period:
            logger.info(f"  Automation Period '{name}' already exists in DB, skipping.")
            continue

        # Resolve the correct profile FK using the JSON's profile_id field, which
        # references the string key used in the profiles dict above.
        json_profile_id = str(per_item.get('profile_id', ''))
        target_profile_db_id = json_id_to_db_id.get(json_profile_id)

        if target_profile_db_id is None:
            # Fall back: use the first available profile rather than silently drop the period
            first_prof = session.query(AutomationProfile).first()
            if not first_prof:
                logger.warning(f"  No profiles in DB; cannot migrate period '{name}'. Skipping.")
                continue
            target_profile_db_id = first_prof.id
            logger.warning(
                f"  Period '{name}' references unknown profile id {json_profile_id!r}; "
                f"assigning to profile id {target_profile_db_id}."
            )

        schedule = per_item.get('schedule', {})
        cron = _build_cron(schedule, per_item)

        period = AutomationPeriod(
            profile_id=target_profile_db_id,
            cron_schedule=cron,
            name=name,
            enabled=per_item.get('enabled', True),
            channel_regex=per_item.get('channel_regex'),
            exclude_regex=per_item.get('exclude_regex'),
            matching_type=per_item.get('matching_type'),
            automation_type=per_item.get('automation_type'),
            extra_settings=per_item.get('extra_settings'),
        )
        session.add(period)
        count_periods += 1
        rows_written += 1

    logger.info(
        f"✓ Migrated {count_profiles} Automation Profiles and {count_periods} Periods "
        f"from {data_dir.name}"
    )
    return rows_written


def migrate_channel_regex(session, data_dir) -> int:
    path = data_dir / 'channel_regex_config.json'
    if not path.exists():
        return 0
    data = load_json(path)
    if not data:
        return 0

    rows_written = 0
    count_configs = 0
    count_patterns = 0

    # Global settings
    global_settings = data.get('global_settings', {})
    if global_settings:
        setting = SystemSetting(key='channel_regex_global_settings', value=global_settings)
        session.merge(setting)
        rows_written += 1

    patterns_dict = data.get('patterns', {})
    for channel_id, item in patterns_dict.items():
        config = ChannelRegexConfig(
            channel_id=str(channel_id),
            name=item.get('name', ''),
            enabled=item.get('enabled', True),
            match_by_tvg_id=item.get('match_by_tvg_id', False)
        )
        session.merge(config)
        session.flush()
        count_configs += 1

        # Clear existing patterns for this channel to prevent duplicates on re-run
        session.query(ChannelRegexPattern).filter(
            ChannelRegexPattern.channel_id == str(channel_id)
        ).delete()

        regex_patterns = item.get('regex_patterns', [])
        for order, p in enumerate(regex_patterns):
            pat = ChannelRegexPattern(
                channel_id=str(channel_id),
                pattern=p.get('pattern'),
                m3u_accounts=p.get('m3u_accounts'),
                step_order=order
            )
            session.add(pat)
            count_patterns += 1
            rows_written += 1

    logger.info(
        f"✓ Migrated {count_configs} Channel Regex Configs with {count_patterns} Patterns "
        f"from {data_dir.name}"
    )
    return rows_written


def migrate_system_settings(session, data_dir) -> int:
    files_to_migrate = [
        ('stream_checker_config.json',  'stream_checker_config'),
        ('auto_create_rules.json',       'auto_create_rules'),
        ('scheduling_config.json',       'scheduling_config'),
        ('dispatcharr_config.json',      'dispatcharr_config'),
        ('session_settings.json',        'session_settings'),
    ]

    rows_written = 0
    for filename, key in files_to_migrate:
        path = data_dir / filename
        if not path.exists():
            continue
        data = load_json(path)
        if not data:
            continue

        setting = SystemSetting(key=key, value=data)
        session.merge(setting)
        rows_written += 1
        logger.info(f"✓ Migrated {filename} -> SystemSetting({key}) from {data_dir.name}")

    return rows_written


def migrate_changelog(session, data_dir) -> int:
    """
    Migrate historical changelog entries to the relational telemetry tables.

    Reuses the same save functions as the live telemetry pipeline so the
    resulting rows are indistinguishable from entries written at runtime.
    """
    path = data_dir / 'changelog.json'
    if not path.exists():
        return 0
    data = load_json(path)
    if not data:
        return 0

    # Import here to avoid circular imports at module load time
    from apps.telemetry.telemetry_db import save_automation_run_telemetry, save_generic_telemetry

    count = 0
    errors = 0
    for entry in data:
        action     = entry.get('action')
        details    = entry.get('details', {})
        subentries = entry.get('subentries')
        timestamp  = entry.get('timestamp')

        try:
            if action == 'automation_run':
                save_automation_run_telemetry(action, details, subentries, timestamp)
            else:
                save_generic_telemetry(action, details, subentries, timestamp)
            count += 1
        except Exception as e:
            errors += 1
            logger.warning(f"  Changelog entry {count + errors} failed to migrate: {e}")

        if (count + errors) % 50 == 0:
            logger.debug(f"  Changelog progress: {count} migrated, {errors} errors")

    logger.info(
        f"✓ Migrated {count} changelog entries from {data_dir.name}"
        + (f" ({errors} entries skipped due to errors)" if errors else "")
    )
    return count


def main():
    logger.info("Starting Data Migration to SQL (Startup check)...")

    init_db()
    session = get_session()
    total_rows_written = 0

    try:
        source_dirs = [
            CONFIG_DIR,
            backend_dir.parent / 'old',
        ]

        logger.info(f"Checking directories for migration: {[str(d) for d in source_dirs]}")

        for data_dir in source_dirs:
            if not data_dir.exists():
                logger.debug(f"Source directory does not exist, skipping: {data_dir}")
                continue

            logger.info(f"Processing directory: {data_dir}")

            # 1. Dead Streams
            if (data_dir / 'dead_streams.json').exists():
                total_rows_written += migrate_dead_streams(session, data_dir)

            # 2. Automation (profiles, periods, global settings)
            if (data_dir / 'automation_config.json').exists():
                total_rows_written += migrate_automation(session, data_dir)

            # 3. Channel Regex
            if (data_dir / 'channel_regex_config.json').exists():
                total_rows_written += migrate_channel_regex(session, data_dir)

            # 4. Generic System Settings
            system_files = [
                'stream_checker_config.json', 'auto_create_rules.json',
                'scheduling_config.json', 'dispatcharr_config.json', 'session_settings.json',
            ]
            if any((data_dir / f).exists() for f in system_files):
                total_rows_written += migrate_system_settings(session, data_dir)

            # 5. Changelog / historical telemetry
            if (data_dir / 'changelog.json').exists():
                total_rows_written += migrate_changelog(session, data_dir)

        if total_rows_written > 0:
            session.commit()
            logger.info(f"MIGRATION SUCCESSFUL! ({total_rows_written} rows written)")

            # Back up and remove every migrated JSON file so this script is a no-op
            # on the next startup rather than re-processing the same data.
            backup_dir = CONFIG_DIR / 'backup'
            backup_dir.mkdir(exist_ok=True)

            for fname in ALL_MIGRATION_FILES:
                fpath = CONFIG_DIR / fname
                if fpath.exists():
                    try:
                        dest = backup_dir / f"{fpath.name}.bak"
                        if dest.exists():
                            dest = backup_dir / f"{fpath.name}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                        fpath.rename(dest)
                        logger.info(f"✓ Backed up: {fpath.name} -> {dest.name}")
                    except Exception as e:
                        logger.warning(f"Failed to back up {fpath.name}: {e}")
        else:
            logger.info("No JSON configuration files pending migration found. Skipping.")

    except Exception as e:
        session.rollback()
        logger.error(f"Migration FAILED: {e}", exc_info=True)
    finally:
        session.close()


if __name__ == '__main__':
    main()
