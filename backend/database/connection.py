import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Configuration directory - persisted via Docker volume
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', str(Path(__file__).parent.parent / 'data')))
DB_PATH = CONFIG_DIR / 'streamflow.db'

# Single declarative base for the entire application
Base = declarative_base()

def get_engine():
    """Returns the SQLAlchemy engine, creating the directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Using SQLite for now (as used in telemetry_db.py)
    # echo=False in production, can be enabled for debugging
    engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
    return engine

def get_session():
    """Returns a new SQLAlchemy session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    """Create all tables if they don't exist."""
    engine = get_engine()
    
    # Import models here to ensure they are registered with Base
    from database.models import (
        Channel, Stream, ChannelGroup, Logo, 
        M3UAccount, M3UAccountProfile,
        channel_streams, group_accounts,
        MatchProfile, MatchProfileStep,
        AutomationProfile, AutomationPeriod,
        MonitoringSession, DeadStream,
        ChannelRegexConfig, ChannelRegexPattern,
    )
    
    Base.metadata.create_all(engine)
    return True
