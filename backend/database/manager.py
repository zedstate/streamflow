import logging
from typing import List, Dict, Optional, Any, Set
from sqlalchemy.orm import Session
from datetime import datetime

from database.connection import get_session
from database.models import (
    Channel, Stream, ChannelGroup, Logo, 
    M3UAccount, M3UAccountProfile,
    channel_streams, group_accounts,
    MatchProfile, MatchProfileStep,
    AutomationProfile, AutomationPeriod,
    MonitoringSession, DeadStream
)

logger = logging.getLogger(__name__)

def _model_to_dict(obj) -> Dict[str, Any]:
    """Helper to convert SQLAlchemy model to dictionary."""
    if not obj:
        return {}
    
    result = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[column.name] = value
    return result

class DatabaseManager:
    """
    Data Access Layer (DAL) Manager.
    
    Provides high-level helpers for CRUD operations, acting as a bridge 
    towards full migration of singletons.
    """
    
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session

    def _get_session(self) -> Session:
        return self.session_factory()

    # === Channels ===

    def get_channels(self, as_dict: bool = True) -> List[Any]:
        """Get all channels."""
        session = self._get_session()
        try:
            channels = session.query(Channel).all()
            if as_dict:
                # We need to load streams relationship too, to match UDI dict structure
                result = []
                for ch in channels:
                    d = _model_to_dict(ch)
                    # Add stream IDs list
                    d['streams'] = [st.id for st in ch.streams]
                    result.append(d)
                return result
            return channels
        finally:
            session.close()

    def get_channel_by_id(self, channel_id: int, as_dict: bool = True) -> Optional[Any]:
        """Get a channel by ID."""
        session = self._get_session()
        try:
            ch = session.query(Channel).filter(Channel.id == channel_id).first()
            if ch and as_dict:
                d = _model_to_dict(ch)
                d['streams'] = [st.id for st in ch.streams]
                return d
            return ch
        finally:
            session.close()

    def update_channel(self, channel_id: int, data: Dict[str, Any]) -> bool:
        """Update or insert a channel."""
        session = self._get_session()
        try:
            ch = session.query(Channel).filter(Channel.id == channel_id).first()
            is_new = False
            if not ch:
                ch = Channel(id=channel_id)
                session.add(ch)
                is_new = True

            # Update fields
            for k, v in data.items():
                if k != 'streams' and hasattr(ch, k):
                    if k in ['updated_at', 'last_seen'] and isinstance(v, str):
                        try: v = datetime.fromisoformat(v)
                        except: pass
                    setattr(ch, k, v)

            # Update stream relationships if present in dict style `streams: [id1, id2]`
            if 'streams' in data:
                stream_ids = data['streams']
                streams = session.query(Stream).filter(Stream.id.in_(stream_ids)).all()
                ch.streams = streams

            session.commit()
            logger.debug(f"{'Created' if is_new else 'Updated'} channel {channel_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating channel {channel_id}: {e}")
            return False
        finally:
            session.close()

    # === Streams ===

    def get_streams(self, as_dict: bool = True) -> List[Any]:
        """Get all streams."""
        session = self._get_session()
        try:
            streams = session.query(Stream).all()
            if as_dict:
                return [_model_to_dict(st) for st in streams]
            return streams
        finally:
            session.close()

    def get_stream_by_id(self, stream_id: int, as_dict: bool = True) -> Optional[Any]:
        """Get a stream by ID."""
        session = self._get_session()
        try:
            st = session.query(Stream).filter(Stream.id == stream_id).first()
            return _model_to_dict(st) if st and as_dict else st
        finally:
            session.close()

    def update_stream(self, stream_id: int, data: Dict[str, Any]) -> bool:
        """Update or insert a stream."""
        session = self._get_session()
        try:
            st = session.query(Stream).filter(Stream.id == stream_id).first()
            is_new = False
            if not st:
                st = Stream(id=stream_id)
                session.add(st)
                is_new = True

            for k, v in data.items():
                if hasattr(st, k):
                    if k in ['updated_at', 'last_seen', 'stats_updated_at'] and isinstance(v, str):
                        try: v = datetime.fromisoformat(v)
                        except: pass
                    setattr(st, k, v)

            session.commit()
            logger.debug(f"{'Created' if is_new else 'Updated'} stream {stream_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating stream {stream_id}: {e}")
            return False
        finally:
            session.close()

    # === Channel Groups ===

    def get_channel_groups(self, as_dict: bool = True) -> List[Any]:
        session = self._get_session()
        try:
            groups = session.query(ChannelGroup).all()
            if as_dict:
                return [_model_to_dict(g) for g in groups]
            return groups
        finally:
            session.close()

    # === Dead Streams Tracker ===

    def mark_stream_dead(self, url: str, stream_id: int, stream_name: str, channel_id: Optional[int] = None, reason: str = 'offline') -> bool:
        session = self._get_session()
        try:
            dead = session.query(DeadStream).filter(DeadStream.url == url).first()
            if not dead:
                dead = DeadStream(url=url)
                session.add(dead)
            
            dead.stream_id = stream_id
            dead.stream_name = stream_name
            dead.channel_id = channel_id
            dead.reason = reason
            dead.marked_dead_at = datetime.utcnow()
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error marking stream dead {url}: {e}")
            return False
        finally:
            session.close()

    def remove_dead_stream(self, url: str) -> bool:
        session = self._get_session()
        try:
            dead = session.query(DeadStream).filter(DeadStream.url == url).first()
            if dead:
                session.delete(dead)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            return False
        finally:
            session.close()

    def is_stream_dead(self, url: str) -> bool:
        session = self._get_session()
        try:
            return session.query(DeadStream).filter(DeadStream.url == url).first() is not None
        finally:
            session.close()

    def get_dead_streams(self, as_dict: bool = True) -> List[Any]:
        session = self._get_session()
        try:
            dead = session.query(DeadStream).all()
            if as_dict:
                # For backward compatibility, return a DICT keyed by URL
                return {d.url: _model_to_dict(d) for d in dead}
            return dead
        finally:
            session.close()

    def count_dead_streams_for_channel(self, channel_id: int) -> int:
        session = self._get_session()
        try:
            return session.query(DeadStream).filter(DeadStream.channel_id == channel_id).count()
        finally:
            session.close()

    def get_dead_streams_for_channel(self, channel_id: int, as_dict: bool = True) -> Any:
        session = self._get_session()
        try:
            dead = session.query(DeadStream).filter(DeadStream.channel_id == channel_id).all()
            if as_dict:
                return {d.url: _model_to_dict(d) for d in dead}
            return dead
        finally:
            session.close()

    def clear_all_dead_streams(self) -> int:
        session = self._get_session()
        try:
            count = session.query(DeadStream).delete()
            session.commit()
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"Error clearing dead streams: {e}")
            return 0
        finally:
            session.close()

    def get_system_setting(self, key: str, default: Any = None) -> Any:
        from database.models import SystemSetting
        session = self._get_session()
        try:
            sett = session.query(SystemSetting).filter(SystemSetting.key == key).first()
            return sett.value if sett else default
        finally:
            session.close()

    def set_system_setting(self, key: str, value: Any):
        from database.models import SystemSetting
        session = self._get_session()
        try:
            sett = session.query(SystemSetting).filter(SystemSetting.key == key).first()
            if sett:
                sett.value = value
            else:
                sett = SystemSetting(key=key, value=value)
                session.add(sett)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error setting system config {key}: {e}")
            return False
        finally:
            session.close()

# Singleton Instance
_db_manager = None

def get_db_manager():
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
