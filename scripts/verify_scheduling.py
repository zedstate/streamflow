#!/usr/bin/env python3
import sys
import json
import time
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:5000/api"

def check_backend_health():
    """Wait for backend to be healthy."""
    logger.info("Checking backend health...")
    for i in range(10):
        try:
            response = requests.get(f"{BASE_URL}/automation/status")
            if response.status_code == 200:
                logger.info("Backend is healthy")
                return True
        except requests.exceptions.ConnectionError:
            pass
        logger.info(f"Waiting for backend... ({i+1}/10)")
        time.sleep(2)
    return False

def verify_global_settings():
    """Verify global settings API endpoints."""
    logger.info("Verifying global settings API...")
    
    # 1. Get current settings
    try:
        response = requests.get(f"{BASE_URL}/settings/automation/global")
        if response.status_code != 200:
            logger.error(f"Failed to get global settings: {response.text}")
            return False
        
        settings = response.json()
        logger.info(f"Current settings: {json.dumps(settings, indent=2)}")
        
        if "global_schedule" not in settings:
            logger.error("global_schedule missing from settings")
            return False
            
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return False

    # 2. Update settings
    new_interval = 45
    logger.info(f"Updating global schedule interval to {new_interval} minutes...")
    
    update_payload = {
        "global_schedule": {
            "type": "interval",
            "value": new_interval
        }
    }
    
    try:
        response = requests.put(f"{BASE_URL}/settings/automation/global", json=update_payload)
        if response.status_code != 200:
            logger.error(f"Failed to update settings: {response.text}")
            return False
            
        # Verify update persisted
        response = requests.get(f"{BASE_URL}/settings/automation/global")
        settings = response.json()
        
        if settings.get("global_schedule", {}).get("value") != new_interval:
            logger.error(f"Settings update failed persistence check. Expected {new_interval}, got {settings.get('global_schedule', {}).get('value')}")
            return False
            
        logger.info("Global settings Interval update verified successfully")
        
        # 3. Update settings (Cron)
        cron_expr = "0 4 * * *"
        logger.info(f"Updating global schedule to Cron: {cron_expr}...")
        
        update_payload_cron = {
            "global_schedule": {
                "type": "cron",
                "value": cron_expr
            }
        }
        
        response = requests.put(f"{BASE_URL}/settings/automation/global", json=update_payload_cron)
        if response.status_code != 200:
            logger.error(f"Failed to update settings (Cron): {response.text}")
            return False
            
        # Verify update persisted
        response = requests.get(f"{BASE_URL}/settings/automation/global")
        settings = response.json()
        
        if settings.get("global_schedule", {}).get("type") != "cron" or settings.get("global_schedule", {}).get("value") != cron_expr:
            logger.error(f"Cron settings update failed persistence check.")
            return False

        logger.info("Global settings Cron update verified successfully")
        
        # Restore default
        requests.put(f"{BASE_URL}/settings/automation/global", json={
            "global_schedule": {"type": "interval", "value": 60}
        })
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return False

if __name__ == "__main__":
    if not check_backend_health():
        logger.error("Backend not available")
        sys.exit(1)
        
    if verify_global_settings():
        logger.info("✅ Verification passed!")
        sys.exit(0)
    else:
        logger.error("❌ Verification failed!")
        sys.exit(1)
