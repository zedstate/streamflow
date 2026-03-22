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
    except:
        return None

def migrate_dead_streams(session, data_dir):
    data = load_json(data_dir / 'dead_streams.json')
    if not data: return
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

def migrate_automation(session, data_dir):
    data = load_json(data_dir / 'automation_config.json')
    if not data: return
    count_profiles = 0
    count_periods = 0
    
    profiles = data.get('profiles', {})
    for p_id, p_item in profiles.items():
        name = p_item.get('name', 'Profile')
        
        # Deduplication check
        existing = session.query(AutomationProfile).filter(AutomationProfile.name == name).first()
        if existing:
            logger.info(f"Automation Profile '{name}' already exists in DB, skipping.")
            continue
            
        extra = {
            'stream_matching': p_item.get('stream_matching'),
            'stream_checking': p_item.get('stream_checking'),
            'scoring_weights': p_item.get('scoring_weights')
        }
        prof = AutomationProfile(
            name=name,
            description=p_item.get('description'),
            enabled=p_item.get('enabled', True),
            parallel_checks=1,
            extra_settings=extra
        )
        session.add(prof)
        session.flush()
        count_profiles += 1
    
    periods = data.get('automation_periods', {})
    for per_id, per_item in periods.items():
        name = per_item.get('name', 'Period')
        
        # Deduplication check
        existing_period = session.query(AutomationPeriod).filter(AutomationPeriod.name == name).first()
        if existing_period:
            logger.info(f"Automation Period '{name}' already exists in DB, skipping.")
            continue
            
        schedule = per_item.get('schedule', {})
        cron = f"*/{schedule.get('value', 20)} * * * *" if schedule.get('type') == 'interval' else '* * * * *'
        
        first_prof = session.query(AutomationProfile).first()
        if not first_prof: continue
        
        period = AutomationPeriod(
            profile_id=first_prof.id,
            cron_schedule=cron,
            name=name,
            enabled=per_item.get('enabled', True)
        )
        session.add(period)
        count_periods += 1
            
    logger.info(f"✓ Migrated {count_profiles} Automation Profiles with {count_periods} Periods from {data_dir.name}")

def migrate_channel_regex(session, data_dir):
    path = data_dir / 'channel_regex_config.json'
    if not path.exists(): return
    data = load_json(path)
    if not data: return
    count_configs = 0
    count_patterns = 0
    
    # Global settings
    global_settings = data.get('global_settings', {})
    if global_settings:
        setting = SystemSetting(key='channel_regex_global_settings', value=global_settings)
        session.merge(setting)
        
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
        session.query(ChannelRegexPattern).filter(ChannelRegexPattern.channel_id == str(channel_id)).delete()
        
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
            
    logger.info(f"✓ Migrated {count_configs} Channel Regex Configs with {count_patterns} Patterns from {data_dir.name}")

def migrate_system_settings(session, data_dir):
    files_to_migrate = [
        ('stream_checker_config.json', 'stream_checker_config'),
        ('auto_create_rules.json', 'auto_create_rules'),
        ('scheduling_config.json', 'scheduling_config'),
        ('dispatcharr_config.json', 'dispatcharr_config'),
        ('session_settings.json', 'session_settings')
    ]
    
    for filename, key in files_to_migrate:
        path = data_dir / filename
        if not path.exists(): continue
        data = load_json(path)
        if not data: continue
        
        setting = SystemSetting(key=key, value=data)
        session.merge(setting)
        logger.info(f"✓ Migrated {filename} to SystemSetting({key}) from {data_dir.name}")

def main():
    logger.info("Starting Data Migration to SQL (Startup check)...")
    
    init_db()
    session = get_session()
    has_changes = False
    
    try:
        source_dirs = [
            CONFIG_DIR,
            backend_dir.parent / 'old'
        ]
        
        logger.info(f"Checking directories for migration: {[str(d) for d in source_dirs]}")
        
        for data_dir in source_dirs:
            if not data_dir.exists():
                logger.debug(f"Source directory does not exist, skipping: {data_dir}")
                continue
                
            logger.info(f"Processing directory: {data_dir}")
            
            # 1. Dead Streams
            dead_streams_path = data_dir / 'dead_streams.json'
            if dead_streams_path.exists():
                migrate_dead_streams(session, data_dir)
                has_changes = True
                
            # 2. Automation
            automation_config_path = data_dir / 'automation_config.json'
            if automation_config_path.exists():
                migrate_automation(session, data_dir)
                has_changes = True
                
            # 3. Channel Regex
            channel_regex_path = data_dir / 'channel_regex_config.json'
            if channel_regex_path.exists():
                migrate_channel_regex(session, data_dir)
                has_changes = True
                
            # 4. System Settings (Generic JSONs)
            system_files = ['stream_checker_config.json', 'auto_create_rules.json', 'scheduling_config.json', 'dispatcharr_config.json', 'session_settings.json']
            if any((data_dir / f).exists() for f in system_files):
                migrate_system_settings(session, data_dir)
                has_changes = True

        if has_changes:
            session.commit()
            logger.info("🏆 MIGRATION SUCCESSFUL!")
            
            backup_dir = CONFIG_DIR / 'backup'
            backup_dir.mkdir(exist_ok=True)
            
            files_to_backup = [CONFIG_DIR / 'dead_streams.json', CONFIG_DIR / 'automation_config.json', CONFIG_DIR / 'channel_regex_config.json']
            for fpath in files_to_backup:
                if fpath.exists():
                    try:
                        dest = backup_dir / f"{fpath.name}.bak"
                        if dest.exists():
                             dest = backup_dir / f"{fpath.name}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                        fpath.rename(dest)
                        logger.info(f"✓ Backed up and moved active: {fpath.name} -> {dest}")
                    except Exception as e:
                        logger.warning(f"Failed to backup {fpath.name}: {e}")
        else:
            logger.info("No JSON configuration files pending migration found. Skipping.")
            
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Migration FAILED: {e}", exc_info=True)
    finally:
        session.close()

if __name__ == '__main__':
    main()
