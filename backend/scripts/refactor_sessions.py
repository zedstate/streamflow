import sys
from pathlib import Path

path = Path("backend/stream_session_manager.py")
if not path.exists():
    print("File not found!")
    sys.exit(1)

with open(path, "r") as f:
    content = f.read()

index_start = content.find("        # Ensure config directory exists")
index_end = content.find("    def _serialize_session(self, session: SessionInfo)")

if index_start == -1 or index_end == -1:
    print("Markers not found in file!")
    sys.exit(1)

head = content[:index_start]
tail = content[index_end:]

new_body = """        from database.manager import get_db_manager
        self.db = get_db_manager()

        # Load settings from SystemSetting
        from database.models import SystemSetting
        from database.connection import get_session
        session = get_session()
        try:
            setting = session.query(SystemSetting).filter(SystemSetting.key == 'session_settings').first()
            data = setting.value if setting else {}
            self.review_duration = data.get('review_duration', 60.0)
            self.loop_review_duration = data.get('loop_review_duration', 600.0)
        finally:
            session.close()

        self._last_streams_refresh = 0
        logger.info("StreamSessionManager initialized with SQL backend")

        self._load_sessions()

    def _load_settings(self): pass
    def save_settings(self): pass

    def get_review_duration(self) -> float: return self.review_duration
    def set_review_duration(self, duration: float):
        self.review_duration = float(duration)
        self._save_settings_to_db()

    def get_loop_review_duration(self) -> float: return self.loop_review_duration
    def set_loop_review_duration(self, duration: float):
        self.loop_review_duration = float(duration)
        self._save_settings_to_db()

    def _save_settings_to_db(self):
        from database.models import SystemSetting
        from database.connection import get_session
        session = get_session()
        try:
            s = session.query(SystemSetting).filter(SystemSetting.key == 'session_settings').first()
            if not s:
                 s = SystemSetting(key='session_settings')
                 session.add(s)
            s.value = {'review_duration': self.review_duration, 'loop_review_duration': self.loop_review_duration}
            session.commit()
        except: session.rollback()
        finally: session.close()

    def _load_sessions(self):
        from database.models import MonitoringSession
        from database.connection import get_session
        session = get_session()
        try:
            m_sessions = session.query(MonitoringSession).all()
            session_groups = {}
            for ms in m_sessions:
                raw = ms.raw_info or {}
                cs_id = raw.get('channel_session_id')
                if cs_id:
                     if cs_id not in session_groups: session_groups[cs_id] = []
                     session_groups[cs_id].append(ms)

            for cs_id, ms_list in session_groups.items():
                if not ms_list: continue
                first_raw = ms_list[0].raw_info
                
                s_info = SessionInfo(
                    session_id=cs_id,
                    channel_id=first_raw.get('channel_id', 0),
                    channel_name=first_raw.get('channel_name', ''),
                    regex_filter=first_raw.get('regex_filter', ''),
                    created_at=first_raw.get('created_at', 0.0),
                    is_active=False
                )
                for k, v in first_raw.items():
                    if hasattr(s_info, k) and k not in ['streams', 'quarantined_stream_ids']:
                         setattr(s_info, k, v)
                if 'quarantined_stream_ids' in first_raw:
                     s_info.quarantined_stream_ids = set(first_raw['quarantined_stream_ids'])

                for ms in ms_list:
                    raw = ms.raw_info or {}
                    stream_id = raw.get('stream_id')
                    if stream_id:
                        from backend.stream_session_manager import StreamInfo
                        # Convert dict values to make sure types align or pass direct
                        # Handle conversion if StreamInfo dataclass accepts kwargs
                        try:
                             s_info.streams[stream_id] = StreamInfo(**{k: v for k,v in raw.items() if k in [f_name for f_name in [f.name for f in StreamInfo.__dataclass_fields__.values()]]})
                        except: pass
                self.sessions[cs_id] = s_info
                self.session_locks[cs_id] = threading.Lock()
            logger.info(f"Loaded {len(self.sessions)} sessions from SQL")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
        finally:
            session.close()

    def _save_sessions(self):
        try:
            import copy
            snapshot = copy.deepcopy(dict(self.sessions))
            def _execute_save(snapshot):
                from database.models import MonitoringSession
                from database.connection import get_session
                session = get_session()
                try:
                    for cs_id, s_info in snapshot.items():
                         # Pack Session Info
                         base_raw = {k: v for k, v in self._serialize_session(s_info).items() if k != 'streams'}
                         base_raw['channel_session_id'] = cs_id
                         
                         for stream_id, stream_info in s_info.streams.items():
                              ms_id = f"{cs_id}_{stream_id}"
                              ms = session.query(MonitoringSession).filter(MonitoringSession.session_id == ms_id).first()
                              if not ms:
                                   ms = MonitoringSession(session_id=ms_id)
                                   session.add(ms)
                              ms.stream_id = stream_id
                              ms.status = stream_info.status
                              ms.current_speed = getattr(stream_info, 'current_speed', 0.0)
                              ms.current_bitrate = getattr(stream_info, 'bitrate', 0)
                              
                              # Combine base_raw with stream info
                              from dataclasses import asdict
                              item_raw = base_raw.copy()
                              item_raw.update(asdict(stream_info) if not isinstance(stream_info, dict) else stream_info)
                              if 'metrics_history' in item_raw: del item_raw['metrics_history']
                              ms.raw_info = item_raw
                    session.commit()
                except Exception as e:
                    session.rollback()
                    logger.error(f"Background save sessions failed: {e}")
                finally: session.close()

            import threading
            threading.Thread(target=_execute_save, args=(snapshot,), daemon=True, name="SessionSaver").start()
        except Exception as e:
            logger.error(f"Failed to trigger save sessions: {e}")

"""

final = head + new_body + tail

with open(path, "w") as f:
    f.write(final)

print("✓ Replaced cleanly")
