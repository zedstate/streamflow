from database.connection import get_engine, get_session, init_db, Base
from database.manager import get_db_manager, DatabaseManager
# Optional: export models for convenience
from database.models import (
    Channel, Stream, ChannelGroup, Logo, 
    M3UAccount, M3UAccountProfile,
    channel_streams, group_accounts,
    MatchProfile, MatchProfileStep,
    AutomationProfile, AutomationPeriod,
    MonitoringSession, DeadStream
)
