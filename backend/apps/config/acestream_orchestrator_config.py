#!/usr/bin/env python3
"""AceStream Orchestrator configuration manager."""

import threading
from typing import Any, Dict, Optional

from apps.core.logging_config import setup_logging

logger = setup_logging(__name__)


class AceStreamOrchestratorConfig:
    """SQL-backed config for orchestrator connectivity."""

    def __init__(self):
        self._lock = threading.RLock()

    def _get_db_config(self) -> Dict[str, Any]:
        from apps.database.manager import get_db_manager

        db = get_db_manager()
        cfg = db.get_system_setting('acestream_orchestrator_config', {})
        return cfg if isinstance(cfg, dict) else {}

    def _save_db_config(self, config: Dict[str, Any]) -> bool:
        from apps.database.manager import get_db_manager

        db = get_db_manager()
        return bool(db.set_system_setting('acestream_orchestrator_config', config))

    def get_host(self) -> str:
        return str(self._get_db_config().get('host') or '').strip()

    def get_port(self) -> Optional[int]:
        raw = self._get_db_config().get('port')
        if raw is None or raw == '':
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def get_api_key(self) -> str:
        return str(self._get_db_config().get('api_key') or '').strip()

    def get_base_url(self) -> Optional[str]:
        host = self.get_host()
        if not host:
            return None

        normalized_host = host.rstrip('/')
        if not normalized_host.startswith('http://') and not normalized_host.startswith('https://'):
            normalized_host = f'http://{normalized_host}'

        port = self.get_port()
        if port is None:
            return normalized_host

        # If host already includes explicit port after scheme, keep it unchanged.
        after_scheme = normalized_host.split('://', 1)[1]
        authority = after_scheme.split('/', 1)[0]
        if ':' in authority:
            return normalized_host

        return f'{normalized_host}:{port}'

    def get_config(self) -> Dict[str, Any]:
        return {
            'host': self.get_host(),
            'port': self.get_port(),
            'has_api_key': bool(self.get_api_key()),
        }

    def update_config(self, host: Optional[str] = None, port: Optional[int] = None, api_key: Optional[str] = None) -> bool:
        with self._lock:
            current = self._get_db_config()

            if host is not None:
                current['host'] = str(host).strip()

            if port is not None:
                if port == '':
                    current['port'] = None
                else:
                    try:
                        parsed = int(port)
                        current['port'] = parsed
                    except (TypeError, ValueError):
                        logger.warning(f'Invalid orchestrator port ignored: {port}')

            if api_key is not None:
                current['api_key'] = str(api_key)

            return self._save_db_config(current)

    def is_configured(self) -> bool:
        return bool(self.get_base_url() and self.get_api_key())


_orchestrator_config: Optional[AceStreamOrchestratorConfig] = None
_config_lock = threading.Lock()


def get_acestream_orchestrator_config() -> AceStreamOrchestratorConfig:
    global _orchestrator_config
    with _config_lock:
        if _orchestrator_config is None:
            _orchestrator_config = AceStreamOrchestratorConfig()
        return _orchestrator_config
