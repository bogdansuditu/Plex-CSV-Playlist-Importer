#!/usr/bin/env python3
"""
Simple test script to verify the connection tester works.
"""

import os
import sys
sys.path.append('.')

from app.services.connection_tester import test_plex_connection

# Test with the current .env configuration
plex_url = "http://172.19.35.2:32400"
plex_token = "bT5v9S7irrXXWSzzA1MU"

print(f"Testing connection to: {plex_url}")
print("=" * 50)

success, working_url, error_info = test_plex_connection(plex_url, plex_token)

if success:
    print(f"✅ SUCCESS: Connected to {working_url}")
    if working_url != plex_url:
        print(f"📝 NOTE: Used fallback URL instead of {plex_url}")
        print(f"💡 Consider updating your .env to: PLEX_URL={working_url}")
else:
    print(f"❌ FAILED: {error_info}")
    print(f"\n🔧 Troubleshooting steps:")
    for i, step in enumerate(error_info.troubleshooting_steps, 1):
        print(f"  {i}. {step}")

print("\n" + "=" * 50)