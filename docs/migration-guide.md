# Configuration Migration Guide

## Overview

StreamFlow version 2.0 introduces a new profile-based automation system that provides more flexibility and control over stream management. This guide explains how to upgrade from the legacy configuration format.

## What's Changed?

### Legacy System (v1.x)
- **Global settings** for all automation features
- **Single configuration** applied to all channels
- **M3U priority** managed in separate file
- **Dispatcharr profiles** for channel targeting (deprecated feature)

### New System (v2.x)
- **Automation Profiles** with per-profile settings
- **Flexible assignment** to individual channels or groups
- **Integrated M3U priority** within each profile
- **Profile-based quality thresholds** and matching rules

## Automatic Migration

**The migration process runs automatically on first startup after upgrade.**

### What Happens

1. **Detection**: System checks if configuration is in legacy format
2. **Backup**: All current config files backed up to `data/migration_backup_<timestamp>/`
3. **Conversion**: Legacy settings converted to a default automation profile
4. **Cleanup**: Deprecated files moved to `legacy_files/` directory
5. **Completion**: New configuration ready to use

### Migration Log

Migration progress is logged to the console and application logs:

```
================================================================================
LEGACY CONFIGURATION DETECTED - STARTING MIGRATION
================================================================================
Step 1/5: Creating backup...
Step 2/5: Loading legacy configurations...
Step 3/5: Converting to new profile-based format...
Step 4/5: Writing new configuration...
Step 5/5: Moving deprecated files to legacy directory...
================================================================================
MIGRATION COMPLETED SUCCESSFULLY
Backup created at: data/migration_backup_20260213_123045/
New profile created: 'Migrated Default Profile'
================================================================================
```

## After Migration

### 1. Review Migrated Profile

Navigate to **Automation Profiles** in the web UI to review your migrated settings:

- All your previous global settings are now in "Migrated Default Profile"
- M3U priority settings preserved
- Automation schedules maintained
- Feature toggles converted to profile settings

### 2. Create Additional Profiles (Optional)

Now you can create multiple profiles for different channels or groups:

- Different quality thresholds per channel
- Separate M3U priority orders
- Custom stream matching rules
- Profile-specific automation schedules

### 3. Assign Profiles

Assign profiles to channels or groups:

- **Channel Assignment**: Specific profile for one channel
- **Group Assignment**: Profile for all channels in a group
- **Default Profile**: Fallback for unassigned channels

##Rollback (If Needed)

If you experience issues after migration, you can rollback to the legacy configuration:

### Automatic Rollback Script

```bash
# Interactive mode (lists all backups)
docker exec streamflow python backend/rollback_config.py

# Direct mode (specify backup directory)
docker exec streamflow python backend/rollback_config.py /app/data/migration_backup_20260213_123045
```

### Manual Rollback

1. Stop the container:
   ```bash
   docker-compose down
   ```

2. Restore files from backup:
   ```bash
   cp data/migration_backup_<timestamp>/* data/
   ```

3. Restart with older version:
   ```bash
   docker-compose up -d
   ```

## Files Affected

### Converted
- `automation_config.json` - Converted to new profile format
- `m3u_priority_config.json` - Integrated into profile, moved to `legacy_files/`

### Deprecated
- `profile_config.json` - No longer used, moved to `legacy_files/`

### Preserved (No Changes)
- `stream_checker_config.json`
- `channel_regex_config.json`
- `dispatcharr_config.json`
- `dead_streams.json`
- All other configuration files

## Troubleshooting

### Migration Didn't Run

**Symptom**: No migration log messages on startup

**Possible Causes**:
- Configuration already in new format
- Config file missing or corrupted

**Solution**: Check `data/automation_config.json` structure

### Migration Failed

**Symptom**: Error messages in logs

**Solution**:
1. Check logs for specific error
2. Ensure `data/` directory is writable
3. Verify backup exists in `data/migration_backup_*/`
4. Contact support with error logs

### Settings Not Preserved

**Symptom**: Some settings missing after migration

**Solution**:
1. Check backup directory for original values
2. Restore using rollback script
3. Manually configure in new UI
4. Report issue with backup files

## Support

If you encounter migration issues:

1. **Check Logs**: Review application logs for errors
2. **Backup Available**: Migration creates automatic backups
3. **Rollback Option**: Use rollback script if needed
4. **Report Issues**: Create GitHub issue with logs

## Benefits of New System

### Flexibility
- Different settings per channel/group
- Multiple profiles for different content types
- Easy bulk assignment

### Control
- Fine-grained quality thresholds
- Separate M3U priorities per use case
- Profile-specific automation toggles

### Scalability
- Better organization for large channel counts
- Easier to manage complex setups
- Cleaner configuration structure
