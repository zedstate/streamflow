import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import logging
from telemetry_db import get_session, Run, ChannelHealth, StreamTelemetry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("--- Testing telemetry re-exports ---")
    session = get_session()
    try:
        runs = session.query(Run).all()
        logger.info(f"Loaded {len(runs)} runs from merged SQL backend")
        for r in runs:
             logger.info(f"Run ID: {r.id} - Type: {r.run_type} - Timestamp: {r.timestamp}")
        
        if len(runs) > 0:
             logger.info("✓ Telemetry mapping verified through wrapped export models successfully!")
        else:
             logger.error("No runs found in test layout!")
             sys.exit(1)
             
    except Exception as e:
        logger.error(f"Failed to query telemetry models: {e}")
        sys.exit(1)
    finally:
        session.close()

    logger.info("Verification FINISHED successfully")

if __name__ == "__main__":
    main()
