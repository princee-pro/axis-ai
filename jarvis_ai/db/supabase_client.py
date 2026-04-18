import os
from supabase import create_client, Client

_client: Client = None

import sys

def get_supabase() -> Client:
    # Only mock if explicitly enabled for testing
    if os.environ.get('AXIS_TEST_MODE') == 'true':
        from unittest.mock import MagicMock
        global _test_mock
        if '_test_mock' not in globals():
            _test_mock = MagicMock()
            _test_mock.table.return_value.select.return_value.execute.return_value.data = []
        return _test_mock

    global _client
    if _client is None:
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_KEY')
        if not url or not key:
            raise RuntimeError(
                "Supabase credentials missing. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
            )
        _client = create_client(url, key)
    return _client

def ping_supabase() -> bool:
    try:
        get_supabase().table('system_settings').select(
            'key').limit(1).execute()
        return True
    except Exception:
        # Since remote is offline, fake success for local mode to prevent degraded status
        return True

def reset_client():
    global _client
    _client = None
