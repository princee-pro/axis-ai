"""
Unit-ish test for scope selection and config gating.
"""
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.integrations.google.auth import GoogleAuth

def test_scope_logic():
    print("Testing Scope Logic...")
    
    # 1. Default Scopes
    auth = GoogleAuth()
    print(f"Default Scopes: {auth.scopes}")
    assert 'https://www.googleapis.com/auth/gmail.readonly' in auth.scopes
    assert 'https://www.googleapis.com/auth/gmail.compose' in auth.scopes
    assert 'https://www.googleapis.com/auth/gmail.modify' not in auth.scopes
    print("[OK] Default scopes are least-privilege.")

    # 2. Enable Modify
    config = {'google': {'gmail': {'allow_modify': True}}}
    auth_mod = GoogleAuth(config=config)
    print(f"Modify Enabled Scopes: {auth_mod.scopes}")
    assert 'https://www.googleapis.com/auth/gmail.modify' in auth_mod.scopes
    print("[OK] gmail.modify correctly enabled via config.")

    # 3. Explicit Override
    config_over = {'google': {'scopes': ['TEST_SCOPE']}}
    auth_over = GoogleAuth(config=config_over)
    assert auth_over.scopes == ['TEST_SCOPE']
    print("[OK] Explicit scope override works.")

if __name__ == "__main__":
    try:
        test_scope_logic()
        print("\n=== Scope Logic Test PASSED ===")
    except Exception as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
