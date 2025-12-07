# app/mpesa/utils.py or wherever your M-Pesa utilities are

import requests
import base64
from datetime import datetime
from django.conf import settings
from requests.auth import HTTPBasicAuth


def get_mpesa_access_token():
    """
    Generate M-Pesa access token using consumer key and secret
    """
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_url = settings.MPESA_AUTH_URL  # Should be: https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials

    try:
        response = requests.get(
            api_url,
            auth=HTTPBasicAuth(consumer_key, consumer_secret),
            timeout=30
        )

        if response.status_code == 200:
            json_response = response.json()
            access_token = json_response.get('access_token')
            print(f"✓ Access token generated successfully")
            return access_token
        else:
            print(f"✗ Failed to get access token: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"✗ Error getting access token: {e}")
        return None


def generate_stk_password(shortcode, passkey, timestamp):
    """
    Generate password for STK push
    Password = Base64(Shortcode + Passkey + Timestamp)
    """
    data_to_encode = f"{shortcode}{passkey}{timestamp}"
    encoded = base64.b64encode(data_to_encode.encode())
    return encoded.decode('utf-8')


def generate_timestamp():
    """
    Generate timestamp in the format: YYYYMMDDHHmmss
    """
    return datetime.now().strftime('%Y%m%d%H%M%S')