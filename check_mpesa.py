# Create a file: check_mpesa.py in your project root
# Run it with: python check_mpesa.py

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')  # Change 'project' to your project name
django.setup()

from django.conf import settings
import requests
from requests.auth import HTTPBasicAuth

print("=" * 70)
print("M-PESA CONFIGURATION CHECK")
print("=" * 70)

# Check if settings exist
required_settings = {
    'MPESA_CONSUMER_KEY': 'Consumer Key',
    'MPESA_CONSUMER_SECRET': 'Consumer Secret',
    'MPESA_SHORTCODE': 'Shortcode',
    'MPESA_PASSKEY': 'Passkey',
    'MPESA_CALLBACK_URL': 'Callback URL',
    'MPESA_AUTH_URL': 'Auth URL',
    'MPESA_STK_PUSH_URL': 'STK Push URL',
}

print("\n1. CHECKING SETTINGS:")
print("-" * 70)

all_present = True
for setting, name in required_settings.items():
    if hasattr(settings, setting):
        value = getattr(settings, setting)
        if 'KEY' in setting or 'SECRET' in setting or 'PASSKEY' in setting:
            display = f"{value[:15]}..." if len(value) > 15 else value
        else:
            display = value
        print(f"✓ {name:20} = {display}")
    else:
        print(f"✗ {name:20} = MISSING!")
        all_present = False

if not all_present:
    print("\n❌ Some settings are missing! Add them to settings.py")
    sys.exit(1)

# Test access token
print("\n2. TESTING ACCESS TOKEN:")
print("-" * 70)

try:
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_url = settings.MPESA_AUTH_URL

    print(f"Request URL: {api_url}")
    print(f"Consumer Key: {consumer_key[:20]}...")
    print(f"Consumer Secret: {consumer_secret[:20]}...")

    response = requests.get(
        api_url,
        auth=HTTPBasicAuth(consumer_key, consumer_secret),
        timeout=30
    )

    print(f"\nResponse Status: {response.status_code}")

    if response.status_code == 200:
        json_response = response.json()
        access_token = json_response.get('access_token')
        print(f"✓ Access Token: {access_token[:30]}...")
        print("\n✅ SUCCESS! Your M-Pesa credentials are working!")
    else:
        print(f"✗ Failed! Response: {response.text}")
        print("\n❌ Your Consumer Key or Secret is incorrect!")
        print("\nTo fix:")
        print("1. Go to https://developer.safaricom.co.ke/")
        print("2. Login > My Apps > Select your app")
        print("3. Copy the Consumer Key and Consumer Secret")
        print("4. Update settings.py with correct values")

except Exception as e:
    print(f"✗ Error: {e}")
    print("\n❌ Failed to connect to M-Pesa API!")

print("\n" + "=" * 70)