import sys
from pathlib import Path

path = Path("backend/telemetry_db.py")
if not path.exists():
    print("File not found!")
    sys.exit(1)

with open(path, "r") as f:
    content = f.read()

index = content.find("def _sanitize_bitrate")
if index == -1:
    print("Marker def _sanitize_bitrate not found!")
    sys.exit(1)

tail = content[index:]

new_head = """import os
import json
from datetime import datetime
from sqlalchemy.orm import sessionmaker

from logging_config import setup_logging
logger = setup_logging(__name__)

# Re-exports from main database context
from database.connection import get_session
from database.models import Run, ChannelHealth, StreamTelemetry

"""

final = new_head + tail

with open(path, "w") as f:
    f.write(final)

print("✓ Refactored telemetry_db.py successfully")
