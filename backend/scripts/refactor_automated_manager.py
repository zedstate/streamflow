import sys
from pathlib import Path

path = Path("backend/automated_stream_manager.py")
if not path.exists():
    print("File not found!")
    sys.exit(1)

with open(path, "r") as f:
    content = f.read()

print("--- Refactoring ChangelogManager.__init__ ---")
# Remove init_db() call
old_init = """        try:
            from telemetry_db import init_db
            init_db()
        except:
            pass"""
new_init = "        pass"
content = content.replace(old_init, new_init)


print("--- Refactoring RegexChannelMatcher ---")
# Replace _load_patterns
old_load_patterns = """    def _load_patterns(self) -> Dict:
        \"\"\"Load regex patterns for channel matching.
        
        Handles corrupted JSON and invalid regex patterns gracefully by:
        - Creating default config if JSON is invalid
        - Removing patterns with invalid regex on load to prevent persistent errors
        - Migrating old format (regex array) to new format (regex_patterns array of objects)
        \"\"\"
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)"""

new_load_patterns = """    def _load_patterns(self) -> Dict:
        \"\"\"Load regex patterns for channel matching from SQL.\"\"\"
        from database.connection import get_session
        from database.models import SystemSetting
        
        session = get_session()
        try:
            setting = session.query(SystemSetting).filter(SystemSetting.key == 'channel_regex_config').first()
            if setting and setting.value:
                loaded_config = setting.value
            else:
                raise Exception("No regex config found in DB")"""

content = content.replace(old_load_patterns, new_load_patterns)

# Replace _save_patterns
old_save_patterns = """    def _save_patterns(self, patterns: Dict):
        \"\"\"Save patterns to file.\"\"\"
        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(patterns, f, indent=2)"""

new_save_patterns = """    def _save_patterns(self, patterns: Dict):
        \"\"\"Save patterns to SQL.\"\"\"
        from database.connection import get_session
        from database.models import SystemSetting
        
        session = get_session()
        try:
            # Upsert
            setting = session.query(SystemSetting).filter(SystemSetting.key == 'channel_regex_config').first()
            if not setting:
                setting = SystemSetting(key='channel_regex_config', value=patterns)
                session.add(setting)
            else:
                # Force flag modified
                from sqlalchemy.orm.attributes import flag_modified
                setting.value = patterns
                flag_modified(setting, "value")
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save regex patterns: {e}")
        finally:
            session.close()"""

content = content.replace(old_save_patterns, new_save_patterns)


print("--- Refactoring AutomatedStreamManager State ---")
# Replace _load_state
old_load_state = """    def _load_state(self) -> Dict[str, datetime]:
        \"\"\"Load persisted automation state from file.\"\"\"
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)"""

new_load_state = """    def _load_state(self) -> Dict[str, datetime]:
        \"\"\"Load persisted automation state from SQL.\"\"\"
        from database.connection import get_session
        from database.models import SystemSetting
        
        session = get_session()
        try:
            setting = session.query(SystemSetting).filter(SystemSetting.key == 'automation_state').first()
            if setting and setting.value:
                state = setting.value
            else:
                raise Exception("No automation state found in DB")"""

content = content.replace(old_load_state, new_load_state)

# Replace _save_state
old_save_state = """    def _save_state(self):
        \"\"\"Save current automation state to file.\"\"\"
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            serializable_runs = {
                pid: dt.isoformat() 
                for pid, dt in self.period_last_run.items() 
                if isinstance(dt, datetime)
            }
            state = {'period_last_run': serializable_runs}
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save automation state: {e}")"""

new_save_state = """    def _save_state(self):
        \"\"\"Save current automation state to SQL.\"\"\"
        from database.connection import get_session
        from database.models import SystemSetting
        try:
            serializable_runs = {
                pid: dt.isoformat() 
                for pid, dt in self.period_last_run.items() 
                if isinstance(dt, datetime)
            }
            state = {'period_last_run': serializable_runs}
            
            session = get_session()
            setting = session.query(SystemSetting).filter(SystemSetting.key == 'automation_state').first()
            if not setting:
                setting = SystemSetting(key='automation_state', value=state)
                session.add(setting)
            else:
                from sqlalchemy.orm.attributes import flag_modified
                setting.value = state
                flag_modified(setting, "value")
            session.commit()
            session.close()
        except Exception as e:
            logger.error(f"Failed to save automation state: {e}")"""

content = content.replace(old_save_state, new_save_state)


print("--- Refactoring AutomatedStreamManager Config ---")
# Replace _load_config
old_load_config = """    def _load_config(self) -> Dict:
        \"\"\"Load automation configuration.\"\"\"
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)"""

new_load_config = """    def _load_config(self) -> Dict:
        \"\"\"Load automation configuration from AutomationConfigManager.\"\"\"
        from automation_config_manager import get_automation_config_manager
        return get_automation_config_manager().get_config()"""

# Replace _save_config
old_save_config = """    def _save_config(self, config: Dict):
        \"\"\"Save configuration to file.\"\"\"
        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)"""

new_save_config = """    def _save_config(self, config: Dict):
        \"\"\"Save configuration via AutomationConfigManager.\"\"\"
        from automation_config_manager import get_automation_config_manager
        get_automation_config_manager().update_config(config)"""

content = content.replace(old_load_config, new_load_config)
content = content.replace(old_save_config, new_save_config)

with open(path, "w") as f:
    f.write(content)

print("✓ Refactored automated_stream_manager.py successfully")
