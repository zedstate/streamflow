#!/usr/bin/env python3
"""
Configuration Rollback Script

Rolls back configuration migration to restore legacy files from backup.
Use this if migration causes issues or needs to be reverted.

Author: StreamFlow
Version: 2.0.0
"""

import json
import shutil
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
CONFIG_DIR = Path(__file__).parent.parent / 'data'


def list_available_backups() -> list:
    """
    List all available migration backup directories.
    
    Returns:
        List of backup directories sorted by timestamp (newest first)
    """
    backup_dirs = []
    for item in CONFIG_DIR.glob('migration_backup_*'):
        if item.is_dir():
            backup_dirs.append(item)
    
    # Sort by timestamp in directory name (newest first)
    backup_dirs.sort(reverse=True)
    return backup_dirs


def restore_from_backup(backup_dir: Path) -> bool:
    """
    Restore configuration files from a backup directory.
    
    Args:
        backup_dir: Path to backup directory
        
    Returns:
        True if restore successful, False otherwise
    """
    if not backup_dir.exists() or not backup_dir.is_dir():
        logger.error(f"Backup directory not found: {backup_dir}")
        return False
    
    logger.info("=" * 80)
    logger.info(f"RESTORING CONFIGURATION FROM BACKUP: {backup_dir.name}")
    logger.info("=" * 80)
    
    try:
        # Create a safety backup before restoring
        safety_backup = CONFIG_DIR / f'pre_rollback_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        safety_backup.mkdir(parents=True, exist_ok=True)
        logger.info(f"Creating safety backup at: {safety_backup}")
        
        # Files to restore
        files_to_restore = [
            'automation_config.json',
            'm3u_priority_config.json',
            'profile_config.json'
        ]
        
        restored_count = 0
        
        for filename in files_to_restore:
            backup_file = backup_dir / filename
            target_file = CONFIG_DIR / filename
            
            # Safety backup of current file if it exists
            if target_file.exists():
                shutil.copy2(target_file, safety_backup / filename)
                logger.info(f"Backed up current {filename} to safety backup")
            
            # Restore from backup if file exists in backup
            if backup_file.exists():
                shutil.copy2(backup_file, target_file)
                logger.info(f"✓ Restored {filename}")
                restored_count += 1
            else:
                logger.warning(f"⚠ File not found in backup: {filename}")
        
        if restored_count > 0:
            logger.info("=" * 80)
            logger.info(f"ROLLBACK COMPLETED SUCCESSFULLY")
            logger.info(f"Restored {restored_count} file(s)")
            logger.info(f"Safety backup created at: {safety_backup}")
            logger.info("=" * 80)
            logger.info("IMPORTANT: Please restart the application for changes to take effect")
            return True
        else:
            logger.error("No files were restored - backup may be incomplete")
            return False
            
    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        return False


def interactive_rollback():
    """
    Interactive rollback process that lists backups and prompts user to select one.
    """
    logger.info("Configuration Rollback Utility")
    logger.info("=" * 80)
    
    # List available backups
    backups = list_available_backups()
    
    if not backups:
        logger.error("No backup directories found in {CONFIG_DIR}")
        logger.info("Migration backups are stored as: migration_backup_YYYYMMDD_HHMMSS")
        return False
    
    # Display available backups
    print("\nAvailable backups:")
    for i, backup in enumerate(backups, 1):
        # Extract timestamp from directory name
        timestamp_str = backup.name.replace('migration_backup_', '')
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
            formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            formatted_time = timestamp_str
        
        print(f"  {i}. {backup.name} ({formatted_time})")
    
    # Prompt user to select backup
    try:
        choice = input(f"\nSelect backup to restore (1-{len(backups)}) or 'q' to quit: ").strip()
        
        if choice.lower() == 'q':
            print("Rollback cancelled")
            return False
        
        index = int(choice) - 1
        if index < 0 or index >= len(backups):
            logger.error(f"Invalid selection: {choice}")
            return False
        
        selected_backup = backups[index]
        
        # Confirm before proceeding
        confirm = input(f"\nRestore from {selected_backup.name}? This will overwrite current configuration. (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Rollback cancelled")
            return False
        
        # Perform rollback
        return restore_from_backup(selected_backup)
        
    except (ValueError, KeyboardInterrupt) as e:
        logger.error(f"Invalid input or cancelled: {e}")
        return False


def main():
    """Main entry point for rollback script."""
    if len(sys.argv) > 1:
        # Non-interactive mode - backup directory specified as argument
        backup_path = Path(sys.argv[1])
        return restore_from_backup(backup_path)
    else:
        # Interactive mode
        return interactive_rollback()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
