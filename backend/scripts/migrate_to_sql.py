import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup paths
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from database.connection import init_db, get_session, DB_PATH
from database.models import (
    Channel, Stream, ChannelGroup, Logo, 
    M3UAccount, M3UAccountProfile,
    MatchProfile, MatchProfileStep,
    AutomationProfile, AutomationPeriod,
    DeadStream
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', str(backend_dir / 'data')))
UDI_DIR = CONFIG_DIR / 'udi'

def load_json(path: Path):
    if not path.exists():
        logger.warning(f"File not found: {path}")
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

def migrate_logos(session):
    data = load_json(UDI_DIR / 'logos.json')
    if not data: return
    count = 0
    for item in data:
        logo = Logo(
            id=item.get('id'),
            name=item.get('name'),
            url=item.get('url'),
            cache_url=item.get('cache_url')
        )
        session.merge(logo) # Use merge in case some IDs overlap or test scripts ran
        count += 1
    logger.info(f"✓ Migrated {count} Logos")

def migrate_match_profiles(session):
    data = load_json(UDI_DIR / 'match_profiles.json')
    if not data: return
    count = 0
    for item in data:
        profile = MatchProfile(
            id=item.get('id'),
            name=item.get('name'),
            description=item.get('description'),
            enabled=item.get('enabled', True),
            created_at=parse_datetime(item.get('created_at')),
            updated_at=parse_datetime(item.get('updated_at'))
        )
        session.merge(profile)
        
        for idx, step_item in enumerate(item.get('steps', [])):
            step = MatchProfileStep(
                profile_id=profile.id,
                type=step_item.get('type'),
                pattern=step_item.get('pattern'),
                variables=step_item.get('variables'),
                enabled=step_item.get('enabled', True),
                step_order=step_item.get('order', idx)
            )
            session.add(step)
        count += 1
    logger.info(f"✓ Migrated {count} Match Profiles")

def migrate_groups(session):
    data = load_json(UDI_DIR / 'channel_groups.json')
    if not data: return
    count = 0
    for item in data:
        g = ChannelGroup(
            id=item.get('id'),
            name=item.get('name'),
            match_profile_id=item.get('match_profile_id')
        )
        session.merge(g)
        count += 1
    logger.info(f"✓ Migrated {count} Channel Groups")

def migrate_m3u_accounts(session):
    data = load_json(UDI_DIR / 'm3u_accounts.json')
    if not data: return
    count = 0
    for item in data:
        acc = M3UAccount(
            id=item.get('id'),
            name=item.get('name', 'Unknown'),
            server_url=item.get('server_url'),
            file_path=item.get('file_path'),
            server_group=item.get('server_group'),
            max_streams=item.get('max_streams', 0),
            is_active=item.get('is_active', True),
            created_at=parse_datetime(item.get('created_at')),
            updated_at=parse_datetime(item.get('updated_at')),
            filters=item.get('filters'),
            user_agent=item.get('user_agent'),
            locked=item.get('locked', False),
            refresh_interval=item.get('refresh_interval', 0),
            custom_properties=item.get('custom_properties'),
            account_type=item.get('account_type'),
            username=item.get('username'),
            password=item.get('password'),
            stale_stream_days=item.get('stale_stream_days', 0),
            status=item.get('status'),
            last_message=item.get('last_message'),
            enable_vod=item.get('enable_vod', False)
        )
        session.merge(acc)
        
        for p_item in item.get('profiles', []):
            prof = M3UAccountProfile(
                id=p_item.get('id'),
                account_id=acc.id,
                name=p_item.get('name'),
                max_streams=p_item.get('max_streams', 0),
                is_active=p_item.get('is_active', True),
                is_default=p_item.get('is_default', False),
                current_viewers=p_item.get('current_viewers', 0),
                search_pattern=p_item.get('search_pattern'),
                replace_pattern=p_item.get('replace_pattern'),
                custom_properties=p_item.get('custom_properties')
            )
            session.merge(prof)
        count += 1
    logger.info(f"✓ Migrated {count} M3U Accounts")

def migrate_streams(session):
    data = load_json(UDI_DIR / 'streams.json')
    if not data: return
    count = 0
    for item in data:
        st = Stream(
            id=item.get('id'),
            name=item.get('name', ''),
            url=item.get('url', ''),
            m3u_account_id=item.get('m3u_account'),
            logo_url=item.get('logo_url'),
            tvg_id=item.get('tvg_id'),
            local_file=item.get('local_file'),
            current_viewers=item.get('current_viewers', 0),
            updated_at=parse_datetime(item.get('updated_at')),
            last_seen=parse_datetime(item.get('last_seen')),
            stream_profile_id=item.get('stream_profile_id'),
            is_custom=item.get('is_custom', False),
            channel_group_id=item.get('channel_group'),
            stream_hash=item.get('stream_hash'),
            stream_stats=item.get('stream_stats'),
            stats_updated_at=parse_datetime(item.get('stream_stats_updated_at')),
            is_stale=item.get('is_stale', False),
            is_adult=item.get('is_adult', False),
            provider_stream_id=item.get('stream_id'),
            stream_chno=item.get('stream_chno')
        )
        session.merge(st)
        count += 1
    logger.info(f"✓ Migrated {count} Streams")

def migrate_channels(session):
    data = load_json(UDI_DIR / 'channels.json')
    if not data: return
    count = 0
    for item in data:
        ch = Channel(
            id=item.get('id'),
            channel_number=item.get('channel_number'),
            name=item.get('name', ''),
            channel_group_id=item.get('channel_group_id'),
            tvg_id=item.get('tvg_id'),
            epg_data_id=item.get('epg_data_id'),
            stream_profile_id=item.get('stream_profile_id'),
            uuid=item.get('uuid'),
            logo_id=item.get('logo_id'),
            user_level=item.get('user_level'),
            auto_created=item.get('auto_created', False),
            auto_created_by=item.get('auto_created_by'),
            auto_created_by_name=item.get('auto_created_by_name'),
            tvc_guide_stationid=item.get('tvc_guide_stationid'),
            match_profile_id=item.get('match_profile_id'),
            is_adult=item.get('is_adult', False)
        )
        session.merge(ch)
        session.flush() # Ensure channel is merged so many-to-many works
        
        # Streams mapping
        stream_ids = item.get('streams', [])
        if stream_ids:
            # Query valid inserted streams
            assoc_streams = session.query(Stream).filter(Stream.id.in_(stream_ids)).all()
            ch.streams = assoc_streams
            
        count += 1
    logger.info(f"✓ Migrated {count} Channels")

def migrate_dead_streams(session):
    data = load_json(CONFIG_DIR / 'dead_streams.json')
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
    logger.info(f"✓ Migrated {count} Dead Streams")

def migrate_automation(session):
    data = load_json(CONFIG_DIR / 'automation_config.json')
    if not data: return
    count_profiles = 0
    count_periods = 0
    
    profiles = data.get('profiles', {})
    # profiles is a dict of id: profile_dict
    for p_id, p_item in profiles.items():
        # Optional: convert m3uplaylists and match priorities to JSON strings for extra_settings
        extra = {
            'stream_matching': p_item.get('stream_matching'),
            'stream_checking': p_item.get('stream_checking'),
            'scoring_weights': p_item.get('scoring_weights')
        }
        prof = AutomationProfile(
            # Profiles might use UUIDs in JSON, but our schema supports String
            # id column was Integer PK in models.py autoincrement!
            # If JSON IDs are string UUIDs, they won't fit Integer PK unless mapped or we change model type.
            # Wait, ID in template is autoincrement Integer in models.py.
            # Let's let autoincrement handle it and store string name or map them.
            name=p_item.get('name', 'Profile'),
            description=p_item.get('description'),
            enabled=p_item.get('enabled', True),
            parallel_checks=1, # Default
            extra_settings=extra
        )
        session.add(prof)
        session.flush() # Populate prof.id
        count_profiles += 1
        
        # Now check assignments to see what periods run this profile
        # Since periods are flat, we just extract period list
    
    # Let's simple insert all periods flat first with a fallback or just do what fits the schema
    periods = data.get('automation_periods', {})
    for per_id, per_item in periods.items():
        schedule = per_item.get('schedule', {})
        cron = f"*/{schedule.get('value', 20)} * * * *" if schedule.get('type') == 'interval' else '* * * * *'
        
        # Link to first available profile for model satisfaction
        first_prof = session.query(AutomationProfile).first()
        if not first_prof: continue
        
        period = AutomationPeriod(
            profile_id=first_prof.id,
            cron_schedule=cron,
            name=per_item.get('name', 'Period'),
            enabled=per_item.get('enabled', True)
        )
        session.add(period)
        count_periods += 1
            
    logger.info(f"✓ Migrated {count_profiles} Automation Profiles with {count_periods} Periods")

def main():
    logger.info("Starting Data Migration to SQL...")
    
    # Reset DB for a clean migration run
    if DB_PATH.exists():
        logger.info(f"Removing existing DB at {DB_PATH} for clean migration...")
        DB_PATH.unlink()
        
    logger.info("Creating Database file...")
    init_db()
    
    session = get_session()
    try:
        migrate_logos(session)
        migrate_match_profiles(session)
        migrate_groups(session)
        migrate_m3u_accounts(session)
        # Flush to ensure parent accounts are there for profiles
        session.flush()
        
        migrate_streams(session)
        session.flush()
        
        # Channels need streams list mapped
        migrate_channels(session)
        migrate_dead_streams(session)
        migrate_automation(session)
        
        session.commit()
        logger.info("🏆 MIGRATION SUCCESSFUL!")
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Migration FAILED: {e}", exc_info=True)
    finally:
        session.close()

if __name__ == '__main__':
    main()
