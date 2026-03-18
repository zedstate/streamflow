import sys
import os
import json
from pathlib import Path

# Add backend to path so we can import modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from telemetry_db import init_db, save_automation_run_telemetry, save_generic_telemetry
from logging_config import setup_logging

logger = setup_logging(__name__)

CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', str(Path(__file__).parent.parent / 'data')))
changelog_path = CONFIG_DIR / 'changelog.json'

def migrate():
    """Migrate historical changelog data to the relational database."""
    init_db()
    
    if not changelog_path.exists():
        logger.info(f"No changelog found at {changelog_path}")
        return
        
    try:
        with open(changelog_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        logger.info(f"Loaded {len(data)} entries from {changelog_path}. Starting migration...")
        
        migrated = 0
        for entry in data:
            action = entry.get('action')
            details = entry.get('details', {})
            subentries = entry.get('subentries')
            timestamp = entry.get('timestamp')
            
            if action == 'automation_run':
                save_automation_run_telemetry(action, details, subentries, timestamp)
            else:
                save_generic_telemetry(action, details, subentries, timestamp)
                
            migrated += 1
            if migrated % 10 == 0:
                logger.debug(f"Migrated {migrated}/{len(data)} entries")
                
        logger.info(f"Successfully migrated {migrated} entries to the database.")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)

if __name__ == "__main__":
    migrate()
