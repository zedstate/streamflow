#!/usr/bin/env python3
"""
M3U Priority Configuration Manager

Manages priority_mode settings for M3U accounts.
This is a StreamFlow-specific configuration that determines how priority bonuses
are applied during stream scoring.

Priority Modes:
- "disabled": No priority bonuses applied. Streams are selected based on quality alone.
- "same_resolution": Priority bonuses applied only within the same resolution group.
  Higher priority accounts' streams will be preferred among streams with identical resolutions.
- "all_streams": Priority bonuses applied to all streams regardless of quality.
  Higher priority accounts' streams will be preferred even if they have lower quality.

The priority value (0-100) from Dispatcharr determines the strength of the bonus.
Higher values give stronger preference to streams from that M3U account.
"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, Optional, Any

from logging_config import setup_logging

logger = setup_logging(__name__)

# Configuration directory
CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data'))
M3U_PRIORITY_CONFIG_FILE = CONFIG_DIR / 'm3u_priority_config.json'


class M3UPriorityConfig:
    """
    Manages M3U account priority mode configuration for StreamFlow.
    
    Handles:
    - priority_mode settings per M3U account
    - Valid modes: "disabled", "same_resolution", "all_streams"
    """
    
    def __init__(self):
        """Initialize the M3U priority configuration manager."""
        self._lock = threading.Lock()
        self._config: Dict[str, Any] = {}
        
        # Reload CONFIG_DIR from environment in case it was changed (for testing)
        global CONFIG_DIR, M3U_PRIORITY_CONFIG_FILE
        CONFIG_DIR = Path(os.environ.get('CONFIG_DIR', '/app/data'))
        M3U_PRIORITY_CONFIG_FILE = CONFIG_DIR / 'm3u_priority_config.json'
        
        self._load_config()
        logger.info("M3U priority configuration manager initialized")
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            if M3U_PRIORITY_CONFIG_FILE.exists():
                with open(M3U_PRIORITY_CONFIG_FILE, 'r') as f:
                    self._config = json.load(f)
                    logger.info("Loaded M3U priority configuration from file")
            else:
                # Initialize with default config
                self._config = {
                    'accounts': {},  # account_id -> priority_mode mapping
                    'global_priority_mode': 'disabled'  # Global priority mode setting
                }
                self._save_config()
                logger.info("Created default M3U priority configuration")
        except Exception as e:
            logger.error(f"Error loading M3U priority configuration: {e}", exc_info=True)
            self._config = {'accounts': {}}
    
    def _save_config(self) -> bool:
        """Save configuration to file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(M3U_PRIORITY_CONFIG_FILE, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info("M3U priority configuration saved to file")
            return True
        except Exception as e:
            logger.error(f"Error saving M3U priority configuration: {e}", exc_info=True)
            return False
    
    def get_priority_mode(self, account_id: int) -> str:
        """Get the priority mode for a specific M3U account.
        
        Falls back to global_priority_mode if no account-specific mode is set.
        
        Args:
            account_id: M3U account ID
            
        Returns:
            Priority mode string ("disabled", "same_resolution", or "all_streams")
        """
        with self._lock:
            # Get account-specific priority mode, or fall back to global setting
            account_mode = self._config.get('accounts', {}).get(str(account_id))
            if account_mode is not None:
                return account_mode
            # Use global priority mode as default
            return self._config.get('global_priority_mode', 'disabled')
    
    def set_priority_mode(self, account_id: int, priority_mode: str) -> bool:
        """Set the priority mode for a specific M3U account.
        
        Args:
            account_id: M3U account ID
            priority_mode: Priority mode ("disabled", "same_resolution", or "all_streams")
            
        Returns:
            True if successful, False otherwise
        """
        valid_modes = ['disabled', 'same_resolution', 'all_streams']
        if priority_mode not in valid_modes:
            logger.error(f"Invalid priority_mode: {priority_mode}. Must be one of: {', '.join(valid_modes)}")
            return False
        
        with self._lock:
            if 'accounts' not in self._config:
                self._config['accounts'] = {}
            
            self._config['accounts'][str(account_id)] = priority_mode
            logger.info(f"Set priority_mode for M3U account {account_id} to {priority_mode}")
            return self._save_config()
    
    def get_all_priority_modes(self) -> Dict[str, str]:
        """Get all priority mode settings.
        
        Returns:
            Dictionary mapping account_id to priority_mode
        """
        with self._lock:
            return self._config.get('accounts', {}).copy()
    
    def get_config(self) -> Dict[str, Any]:
        """Get complete priority configuration.
        
        Returns:
            Complete configuration dictionary
        """
        with self._lock:
            return self._config.copy()
    
    def get_global_priority_mode(self) -> str:
        """Get the global priority mode setting.
        
        Returns:
            Global priority mode string ("disabled", "same_resolution", or "all_streams")
        """
        with self._lock:
            return self._config.get('global_priority_mode', 'disabled')
    
    def set_global_priority_mode(self, priority_mode: str) -> bool:
        """Set the global priority mode.
        
        Args:
            priority_mode: Priority mode ("disabled", "same_resolution", or "all_streams")
            
        Returns:
            True if successful, False otherwise
        """
        valid_modes = ['disabled', 'same_resolution', 'all_streams']
        if priority_mode not in valid_modes:
            logger.error(f"Invalid global priority_mode: {priority_mode}. Must be one of: {', '.join(valid_modes)}")
            return False
        
        with self._lock:
            self._config['global_priority_mode'] = priority_mode
            logger.info(f"Set global priority_mode to {priority_mode}")
            return self._save_config()


# Singleton instance
_m3u_priority_config_instance: Optional[M3UPriorityConfig] = None
_m3u_priority_config_lock = threading.Lock()


def get_m3u_priority_config() -> M3UPriorityConfig:
    """Get or create the singleton M3U priority configuration instance.
    
    Returns:
        M3UPriorityConfig instance
    """
    global _m3u_priority_config_instance
    
    if _m3u_priority_config_instance is None:
        with _m3u_priority_config_lock:
            if _m3u_priority_config_instance is None:
                _m3u_priority_config_instance = M3UPriorityConfig()
    
    return _m3u_priority_config_instance
