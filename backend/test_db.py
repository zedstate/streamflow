import os
import sys
from pathlib import Path

# Set environment variable to use the local DB
data_dir = str(Path(__file__).parent.parent / 'data')
os.environ['CONFIG_DIR'] = data_dir

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from apps.database.connection import init_db

print(f"Initializing DB with CONFIG_DIR={os.environ['CONFIG_DIR']}")
try:
    init_db()
    print("init_db() executed successfully")
except Exception as e:
    print(f"init_db() failed: {e}")
    import traceback
    traceback.print_exc()
