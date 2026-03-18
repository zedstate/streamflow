import sys
from pathlib import Path

path = Path("backend/automation_config_manager.py")
if not path.exists():
    print("File not found!")
    sys.exit(1)

with open(path, "r") as f:
    content = f.read()

# Locate index where we want to overwrite.
# We want to replace from line 65 start of update_global_settings which we know looks like:
# def update_global_settings(self, regular_automation_enabled: Optional[bool] = None, settings: Dict[str, Any] = None) -> bool:
index = content.find("    def update_global_settings")

if index == -1:
    print("Marker not found in file!")
    sys.exit(1)

# Slice and replace EVERYTHING from line 65 down
head = content[:index]

new_body = """    def update_global_settings(self, regular_automation_enabled: Optional[bool] = None, settings: Dict[str, Any] = None) -> bool:
""" + """        updates = settings or {}
        if isinstance(regular_automation_enabled, dict):
            updates.update(regular_automation_enabled)
        elif regular_automation_enabled is not None:
            updates["regular_automation_enabled"] = regular_automation_enabled
            
        if "regular_automation_enabled" in updates:
            self._set_config_dict("regular_automation_enabled", bool(updates["regular_automation_enabled"]))
        
        if "validate_existing_streams" in updates:
            self._set_config_dict("validate_existing_streams", bool(updates["validate_existing_streams"]))

        if "playlist_update_interval_minutes" in updates:
            new_val = updates["playlist_update_interval_minutes"]
            val_wrap = {"type": "interval", "value": new_val} if isinstance(new_val, int) else new_val
            self._set_config_dict("playlist_update_interval_minutes", val_wrap)

        return True

    def _profile_to_dict(self, p) -> dict:
        if not p: return None
        res = {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "enabled": p.enabled,
            "parallel_checks": p.parallel_checks
        }
        if p.extra_settings:
            res.update(p.extra_settings)
        return res

    def _period_to_dict(self, per) -> dict:
        if not per: return None
        res = {
            "id": str(per.id),
            "name": per.name,
            "cron_schedule": per.cron_schedule,
            "enabled": per.enabled,
            "channel_regex": per.channel_regex,
            "exclude_regex": per.exclude_regex,
            "matching_type": per.matching_type,
            "automation_type": per.automation_type,
            "schedule": {"type": "cron", "value": per.cron_schedule} # Standard fallback shape
        }
        if per.extra_settings:
            res.update(per.extra_settings)
        return res

    # --- Profile Management ---

    def get_all_profiles(self) -> List[Dict]:
        from database.models import AutomationProfile
        from database.connection import get_session
        session = get_session()
        try:
            profiles = session.query(AutomationProfile).all()
            return [self._profile_to_dict(p) for p in profiles]
        finally:
            session.close()

    def get_profile(self, profile_id: str) -> Optional[Dict]:
        from database.models import AutomationProfile
        from database.connection import get_session
        if not profile_id: return None
        try: pid = int(profile_id)
        except: return None
        session = get_session()
        try:
            p = session.query(AutomationProfile).filter(AutomationProfile.id == pid).first()
            return self._profile_to_dict(p)
        finally:
            session.close()

    def create_profile(self, profile_data: Dict) -> Optional[str]:
        from database.models import AutomationProfile
        from database.connection import get_session
        session = get_session()
        try:
            # isolate extra settings
            extra = {}
            for k,v in profile_data.items():
                if k not in ['name', 'description', 'enabled', 'parallel_checks']:
                    extra[k] = v
            
            p = AutomationProfile(
                name=profile_data.get("name", "New Profile"),
                description=profile_data.get("description", ""),
                enabled=profile_data.get("enabled", True),
                parallel_checks=profile_data.get("parallel_checks", 1),
                extra_settings=extra
            )
            session.add(p)
            session.commit()
            return str(p.id)
        except Exception as e:
            session.rollback()
            return None
        finally:
            session.close()

    def update_profile(self, profile_id: str, profile_data: Dict) -> bool:
        from database.models import AutomationProfile
        from database.connection import get_session
        try: pid = int(profile_id)
        except: return False
        session = get_session()
        try:
            p = session.query(AutomationProfile).filter(AutomationProfile.id == pid).first()
            if not p: return False
            
            if "name" in profile_data: p.name = profile_data["name"]
            if "description" in profile_data: p.description = profile_data["description"]
            if "enabled" in profile_data: p.enabled = profile_data["enabled"]
            
            # Merge extra_settings
            current_extra = p.extra_settings or {}
            for k,v in profile_data.items():
                if k not in ['name', 'description', 'enabled', 'parallel_checks', 'id']:
                    current_extra[k] = v
            p.extra_settings = current_extra
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def delete_profile(self, profile_id: str) -> bool:
        from database.models import AutomationProfile
        from database.connection import get_session
        try: pid = int(profile_id)
        except: return False
        session = get_session()
        try:
            p = session.query(AutomationProfile).filter(AutomationProfile.id == pid).first()
            if not p: return False
            session.delete(p)
            session.commit()
            
            # Clean assignments from SystemSetting JSON blobs
            assignments = self._get_config_dict("channel_period_assignments", {})
            for c in list(assignments.keys()):
                if assignments[c] == str(pid): del assignments[c]
            self._set_config_dict("channel_period_assignments", assignments)
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    # --- Assignments --- (Uses SystemSetting JSON Blob for compatibility speed)

    def assign_profile_to_channel(self, channel_id: int, profile_id: Optional[str]) -> bool:
        assignments = self._get_config_dict("channel_assignments", {})
        cid = str(channel_id)
        if profile_id is None:
            if cid in assignments: del assignments[cid]
        else:
            assignments[cid] = str(profile_id)
        return self._set_config_dict("channel_assignments", assignments)

    def assign_profile_to_channels(self, channel_ids: List[int], profile_id: Optional[str]) -> bool:
        assignments = self._get_config_dict("channel_assignments", {})
        changed = False
        for cid_raw in channel_ids:
            cid = str(cid_raw)
            if profile_id is None:
                if cid in assignments: 
                    del assignments[cid]
                    changed = True
            else:
                if assignments.get(cid) != str(profile_id):
                    assignments[cid] = str(profile_id)
                    changed = True
        if changed:
            return self._set_config_dict("channel_assignments", assignments)
        return True

    def assign_profile_to_group(self, group_id: int, profile_id: Optional[str]) -> bool:
        assignments = self._get_config_dict("group_assignments", {})
        gid = str(group_id)
        if profile_id is None:
            if gid in assignments: del assignments[gid]
        else:
            assignments[gid] = str(profile_id)
        return self._set_config_dict("group_assignments", assignments)
            
    def get_channel_assignment(self, channel_id: int) -> Optional[str]:
        assignments = self._get_config_dict("channel_assignments", {})
        return assignments.get(str(channel_id))

    def get_group_assignment(self, group_id: int) -> Optional[str]:
        assignments = self._get_config_dict("group_assignments", {})
        return assignments.get(str(group_id))

    def get_effective_profile_id(self, channel_id: int, group_id: Optional[int] = None) -> Optional[str]:
        cid = str(channel_id)
        channel_assignments = self._get_config_dict("channel_assignments", {})
        if cid in channel_assignments:
            return channel_assignments[cid]
        if group_id is not None:
             group_assignments = self._get_config_dict("group_assignments", {})
             gid = str(group_id)
             if gid in group_assignments: return group_assignments[gid]
        return None

    def get_effective_profile(self, channel_id: int, group_id: Optional[int] = None) -> Optional[Dict]:
        pid = self.get_effective_profile_id(channel_id, group_id)
        if pid: return self.get_profile(pid)
        return None

    # --- Automation Periods Management ---

    def get_all_periods(self) -> List[Dict]:
        from database.models import AutomationPeriod
        from database.connection import get_session
        session = get_session()
        try:
            pers = session.query(AutomationPeriod).all()
            return [self._period_to_dict(p) for p in pers]
        finally:
            session.close()

    def get_period(self, period_id: str) -> Optional[Dict]:
        from database.models import AutomationPeriod
        from database.connection import get_session
        try: pid = int(period_id)
        except: return None
        session = get_session()
        try:
            p = session.query(AutomationPeriod).filter(AutomationPeriod.id == pid).first()
            return self._period_to_dict(p)
        finally:
            session.close()

    def create_period(self, period_data: Dict) -> Optional[str]:
        from database.models import AutomationPeriod
        from database.connection import get_session
        session = get_session()
        try:
            sched = period_data.get("schedule", {})
            cron = sched.get("value") if isinstance(sched, dict) else period_data.get("cron_schedule", "0 * * * *")
            
            p = AutomationPeriod(
                name=period_data.get("name", "New Period"),
                profile_id=int(period_data.get("profile_id", 1)), # Or find general
                cron_schedule=cron,
                enabled=period_data.get("enabled", True),
                channel_regex=period_data.get("channel_regex"),
                exclude_regex=period_data.get("exclude_regex"),
                matching_type=period_data.get("matching_type"),
                automation_type=period_data.get("automation_type"),
                extra_settings=period_data.get("extra_settings", {})
            )
            session.add(p)
            session.commit()
            return str(p.id)
        except Exception as e:
            session.rollback()
            return None
        finally:
            session.close()

    def update_period(self, period_id: str, period_data: Dict) -> bool:
        from database.models import AutomationPeriod
        from database.connection import get_session
        try: pid = int(period_id)
        except: return False
        session = get_session()
        try:
            p = session.query(AutomationPeriod).filter(AutomationPeriod.id == pid).first()
            if not p: return False
            
            if "name" in period_data: p.name = period_data["name"]
            if "cron_schedule" in period_data: p.cron_schedule = period_data["cron_schedule"]
            if "schedule" in period_data:
                sched = period_data["schedule"]
                if isinstance(sched, dict) and "value" in sched:
                    p.cron_schedule = sched["value"]
            if "enabled" in period_data: p.enabled = period_data["enabled"]
            if "profile_id" in period_data: p.profile_id = int(period_data["profile_id"])
            if "channel_regex" in period_data: p.channel_regex = period_data["channel_regex"]
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def delete_period(self, period_id: str) -> bool:
        from database.models import AutomationPeriod
        from database.connection import get_session
        try: pid = int(period_id)
        except: return False
        session = get_session()
        try:
            p = session.query(AutomationPeriod).filter(AutomationPeriod.id == pid).first()
            if not p: return False
            session.delete(p)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def assign_period_to_channels(self, period_id: str, channel_ids: List[int], profile_id: str, replace: bool = False) -> bool:
        assignments = self._get_config_dict("channel_period_assignments", {})
        pid = str(period_id)
        changed = False
        for cid_raw in channel_ids:
            cid = str(cid_raw)
            if cid not in assignments: assignments[cid] = {}
            assignments[cid][pid] = str(profile_id)
            changed = True
        if changed:
            return self._set_config_dict("channel_period_assignments", assignments)
        return True

    def remove_period_from_channels(self, period_id: str, channel_ids: List[int]) -> bool:
        assignments = self._get_config_dict("channel_period_assignments", {})
        pid = str(period_id)
        changed = False
        for cid_raw in channel_ids:
            cid = str(cid_raw)
            if cid in assignments and pid in assignments[cid]:
                del assignments[cid][pid]
                if not assignments[cid]: del assignments[cid]
                changed = True
        if changed:
            return self._set_config_dict("channel_period_assignments", assignments)
        return True

    def get_channel_periods(self, channel_id: int) -> Dict[str, str]:
        assignments = self._get_config_dict("channel_period_assignments", {})
        return assignments.get(str(channel_id), {})

    def get_period_channels(self, period_id: str) -> List[int]:
        assignments = self._get_config_dict("channel_period_assignments", {})
        pid = str(period_id)
        res = []
        for cid, pers in assignments.items():
            if pid in pers: res.append(int(cid))
        return res

    def is_period_active_now(self, period_id: str) -> bool:
        return True # Handled by outer scheduler triggers

    def get_active_periods_for_channel(self, channel_id: int) -> List[Dict]:
        pid_profile = self.get_channel_periods(channel_id)
        res = []
        for pid, profile_id in pid_profile.items():
            period = self.get_period(pid)
            if period:
                period_with_profile = period.copy()
                period_with_profile["profile"] = self.get_profile(profile_id)
                period_with_profile["profile_id"] = profile_id
                res.append(period_with_profile)
        return res

    def get_effective_configuration(self, channel_id: int, group_id: Optional[int] = None) -> Optional[Dict]:
        active_periods = self.get_active_periods_for_channel(channel_id)
        if active_periods:
            if len(active_periods) > 1:
                 active_periods.sort(key=lambda p: (-int(p.get('priority', 0)), p.get('id', '')))
            period = active_periods[0]
            profile = period.get('profile')
            if profile:
                 return {
                    'source': 'period',
                    'periods': active_periods,
                    'period_id': period.get('id'),
                    'period_name': period.get('name'),
                    'profile': profile
                 }
        return None

    def _invalidate_events_cache(self):
        try:
            from automation_events_scheduler import get_events_scheduler
            scheduler = get_events_scheduler()
            scheduler.invalidate_cache()
        except: pass

# Singleton instance
_automation_config_manager = None
_manager_lock = threading.Lock()

def get_automation_config_manager() -> AutomationConfigManager:
    global _automation_config_manager
    if _automation_config_manager is None:
        with _manager_lock:
            if _automation_config_manager is None:
                _automation_config_manager = AutomationConfigManager()
    return _automation_config_manager
\"\"\"

final = head + new_body
marker + "\n" + new_body

with open(path, "w") as f:
    f.write(final)

print("✓ Replaced bottom half of AutomationConfigManager successfully")
