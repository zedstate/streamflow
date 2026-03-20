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
from apps.database.models import DeadStream, AutomationProfile, AutomationPeriod

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', str(backend_dir / 'data')))

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
    for p_id, p_item in profiles.items():
        extra = {
            'stream_matching': p_item.get('stream_matching'),
            'stream_checking': p_item.get('stream_checking'),
            'scoring_weights': p_item.get('scoring_weights')
        }
        prof = AutomationProfile(
            name=p_item.get('name', 'Profile'),
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
        schedule = per_item.get('schedule', {})
        cron = f"*/{schedule.get('value', 20)} * * * *" if schedule.get('type') == 'interval' else '* * * * *'
        
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
    logger.info("Starting Data Migration to SQL (Startup check)...")
    
    # Do not Reset/Remove DB on startup runs!
    init_db()
    
    session = get_session()
    has_changes = False
    try:
        dead_streams_path = CONFIG_DIR / 'dead_streams.json'
        automation_config_path = CONFIG_DIR / 'automation_config.json'

        if dead_streams_path.exists():
            migrate_dead_streams(session)
            has_changes = True
            
        if automation_config_path.exists():
            migrate_automation(session)
            has_changes = True
            
        if has_changes:
            session.commit()
            logger.info("🏆 MIGRATION SUCCESSFUL!")
            
            # Backup file cleanup
            backup_dir = CONFIG_DIR / 'backup'
            backup_dir.mkdir(exist_ok=True)
            
            files_to_backup = [dead_streams_path, automation_config_path]
            for fpath in files_to_backup:
                if fpath.exists():
                    try:
                        dest = backup_dir / f"{fpath.name}.bak"
                        if dest.exists():
                             dest = backup_dir / f"{fpath.name}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                        fpath.rename(dest)
                        logger.info(f"✓ Backed up and moved: {fpath.name} -> {dest}")
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
