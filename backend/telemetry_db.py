import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from logging_config import setup_logging

logger = setup_logging(__name__)

# Configuration directory - persisted via Docker volume
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', str(Path(__file__).parent.parent / 'data')))
DB_PATH = CONFIG_DIR / 'telemetry.db'

Base = declarative_base()

class Run(Base):
    __tablename__ = 'runs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    duration_seconds = Column(Float, nullable=False, default=0.0)
    total_channels = Column(Integer, nullable=False, default=0)
    global_dead_count = Column(Integer, nullable=False, default=0)
    global_revived_count = Column(Integer, nullable=False, default=0)
    run_type = Column(String(50), nullable=False, default='automation_run') # 'automation_run', 'playlist_refresh', 'single_channel_check', etc.

    channel_healths = relationship("ChannelHealth", back_populates="run", cascade="all, delete-orphan")
    stream_telemetries = relationship("StreamTelemetry", back_populates="run", cascade="all, delete-orphan")


class ChannelHealth(Base):
    __tablename__ = 'channel_health'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('runs.id', ondelete='CASCADE'), nullable=False, index=True)
    channel_id = Column(Integer, nullable=False, index=True)
    channel_name = Column(String(255), nullable=True) # Useful for quick display without joins
    offline = Column(Boolean, nullable=False, default=False)
    available_streams = Column(Integer, nullable=False, default=0)
    dead_streams = Column(Integer, nullable=False, default=0)
    
    run = relationship("Run", back_populates="channel_healths")


class StreamTelemetry(Base):
    __tablename__ = 'stream_telemetry'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('runs.id', ondelete='CASCADE'), nullable=False, index=True)
    channel_id = Column(Integer, nullable=False, index=True)
    provider_id = Column(Integer, nullable=True, index=True) # M3U Account ID
    stream_id = Column(Integer, nullable=False, index=True)  # Internal UDI stream ID

    bitrate_kbps = Column(Integer, nullable=True)
    resolution_width = Column(Integer, nullable=True)
    resolution_height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    codec = Column(String(50), nullable=True)
    audio_codec = Column(String(50), nullable=True)
    quality_score = Column(Float, nullable=True)
    is_dead = Column(Boolean, nullable=False, default=False)
    is_hdr = Column(Boolean, nullable=False, default=False)
    
    run = relationship("Run", back_populates="stream_telemetries")

# Create compound indices if we need them, e.g., for fast dashboard querying:
Index('idx_stream_provider', StreamTelemetry.provider_id, StreamTelemetry.channel_id)


def get_engine():
    """Returns the SQLAlchemy engine, creating the directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Using SQLite
    engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
    return engine

def init_db():
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info(f"Initialized Telemetry Database at {DB_PATH}")

def get_session():
    """Returns a new SQLAlchemy session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def _sanitize_bitrate(bitrate_str):
    if not bitrate_str:
        return None
    try:
        if isinstance(bitrate_str, (int, float)):
            return int(bitrate_str)
        s = str(bitrate_str).lower().replace(' ', '')
        if 'mbps' in s:
            return int(float(s.replace('mbps', '')) * 1000)
        elif 'kbps' in s:
            return int(float(s.replace('kbps', '')))
        return int(float(s))
    except ValueError:
        return None

def _sanitize_fps(fps_str):
    if not fps_str:
        return None
    try:
        if isinstance(fps_str, (int, float)):
            return float(fps_str)
        s = str(fps_str).lower().replace(' fps', '').strip()
        return float(s)
    except ValueError:
        return None

def _sanitize_resolution(res_str):
    if not res_str or 'x' not in str(res_str).lower():
        return None, None
    try:
        parts = str(res_str).lower().split('x')
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None

def _get_provider_id(m3u_account_name, session):
    # Depending on how the system stores providers, this can be complex.
    # For now, m3u_account_name is passed as a string or sometimes ID. Try to parse ID.
    from udi import get_udi_manager
    if isinstance(m3u_account_name, int):
        return m3u_account_name
    
    # Try looking up via UDI
    udi = get_udi_manager()
    accounts = udi.get_m3u_accounts()
    if accounts:
        for acc in accounts:
            if acc.get('name') == m3u_account_name:
                return acc.get('id')
    return None

def save_automation_run_telemetry(action, details, subentries=None, timestamp=None):
    """
    Parses the raw JSON details and inserts to the relational database.
    Replaces ChangelogManager logic.
    """
    session = get_session()
    try:
        run_ts = datetime.utcnow()
        if timestamp:
            try:
                run_ts = datetime.fromisoformat(timestamp)
            except:
                pass

        # Create Run record
        duration = details.get('duration_seconds', 0.0)
        global_stats = details.get('global_stats', {})
        run = Run(
            timestamp=run_ts,
            duration_seconds=duration,
            total_channels=global_stats.get('total_channels_processed', 0),
            global_dead_count=global_stats.get('total_dead_streams', 0),
            global_revived_count=global_stats.get('total_revived_streams', 0),
            run_type=action
        )
        session.add(run)
        session.flush() # Get run.id

        # Process automation_run structure
        summary = details.get('summary', {})
        periods = summary.get('periods', [])
        
        for p in periods:
            for c in p.get('channels', []):
                channel_id = c.get('channel_id')
                channel_name = c.get('channel_name')
                
                channel_health = ChannelHealth(
                    run_id=run.id,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    offline=False, # We don't have exactly this logic yet, maybe if available_streams==0
                    available_streams=0,
                    dead_streams=0
                )
                session.add(channel_health)
                session.flush()
                
                for step in c.get('steps', []):
                    if step.get('step') == 'Quality Check':
                        step_details = step.get('details', {})
                        dead_streams = step_details.get('dead_streams', [])
                        checked_streams = step_details.get('checked_streams', [])
                        
                        channel_health.dead_streams += len(dead_streams)
                        channel_health.available_streams += len(checked_streams)
                        channel_health.offline = (channel_health.available_streams == 0 and channel_health.dead_streams > 0)
                        
                        # Process dead streams
                        for ds in dead_streams:
                            dtel = StreamTelemetry(
                                run_id=run.id,
                                channel_id=channel_id,
                                stream_id=ds.get('id', 0) if 'id' in ds else ds.get('stream_id', 0),
                                is_dead=True
                            )
                            session.add(dtel)
                        
                        # Process checked (healthy) streams
                        for cs in checked_streams:
                            width, height = _sanitize_resolution(cs.get('resolution'))
                            provider_ident = cs.get('m3u_account')
                            dtel = StreamTelemetry(
                                run_id=run.id,
                                channel_id=channel_id,
                                stream_id=cs.get('stream_id', 0),
                                provider_id=_get_provider_id(provider_ident, session),
                                bitrate_kbps=_sanitize_bitrate(cs.get('bitrate')),
                                resolution_width=width,
                                resolution_height=height,
                                fps=_sanitize_fps(cs.get('fps')),
                                codec=cs.get('video_codec'),
                                audio_codec=cs.get('audio_codec'),
                                quality_score=cs.get('score'),
                                is_dead=False,
                                is_hdr=bool(cs.get('hdr_format') or cs.get('is_hdr'))
                            )
                            session.add(dtel)
                            
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving telemetry data: {e}", exc_info=True)
    finally:
        session.close()

def save_generic_telemetry(action, details, subentries=None, timestamp=None):
    """
    Fallback method to handle single checks or older playlist updates.
    Parse subentries to save stream telemetry.
    """
    session = get_session()
    try:
        run_ts = datetime.utcnow()
        if timestamp:
            try:
                run_ts = datetime.fromisoformat(timestamp)
            except: pass

        run = Run(
            timestamp=run_ts,
            duration_seconds=details.get('duration_seconds', 0.0),
            total_channels=details.get('total_channels', 0) or details.get('total_channels_processed', 0),
            global_dead_count=details.get('total_dead_streams', 0) or details.get('dead_streams', 0),
            global_revived_count=details.get('total_revived_streams', 0),
            run_type=action
        )
        session.add(run)
        session.flush()

        if subentries:
            for group in subentries:
                if group.get('group') == 'check':
                    for item in group.get('items', []):
                        cid = item.get('channel_id')
                        cname = item.get('channel_name')
                        stats = item.get('stats', {})
                        
                        ch = ChannelHealth(
                            run_id=run.id,
                            channel_id=cid,
                            channel_name=cname,
                            available_streams=stats.get('total_streams', 0) - stats.get('dead_streams', 0),
                            dead_streams=stats.get('dead_streams', 0)
                        )
                        session.add(ch)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error saving generic telemetry: {e}", exc_info=True)
    finally:
        session.close()

