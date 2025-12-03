#!/usr/bin/env python
"""Test registration flow with the fixed app."""

import requests
from datetime import datetime

BASE_URL = "http://127.0.0.1:8888"

# Get the home page to establish a session
print("1. Fetching home page...")
session = requests.Session()
response = session.get(f"{BASE_URL}/")
print(f"   Status: {response.status_code}")

# Attempt registration
print("\n2. Attempting registration...")
registration_data = {
    "first_name": "Test",
    "last_name": "User",
    "email": "testuser@example.com",
    "password": "Password123!",
    "confirm_password": "Password123!"
}

response = session.post(f"{BASE_URL}/register", data=registration_data)
print(f"   Status: {response.status_code}")

# Check if registration was successful (redirect expected)
if response.status_code == 200:
    if "Account aangemaakt" in response.text or "ingelogd" in response.text:
        print("   ✓ Registration successful!")
    elif "error" in response.text.lower():
        print("   ✗ Registration error detected in response")
        # Print the error message
        import re
        errors = re.findall(r'<div[^>]*flash[^>]*>([^<]+)</div>', response.text)
        for err in errors:
            print(f"     Error: {err}")
    else:
        print("   ? Unclear response")
else:
    print(f"   ✗ Unexpected status code: {response.status_code}")

# Check if session cookie was set (indicates successful login)
if session.cookies:
    print(f"\n3. Session established: {len(session.cookies)} cookies")
else:
    print(f"\n3. No session cookies (may indicate failed login)")

print("\n✓ Test completed!")
