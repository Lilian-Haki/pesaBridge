import requests
import base64
from datetime import datetime
from django.conf import settings

def get_mpesa_access_token():
    """Get OAuth token from M-Pesa"""
    key = settings.MPESA_ENV["CONSUMER_KEY"]
    secret = settings.MPESA_ENV["CONSUMER_SECRET"]
    response = requests.get(
        settings.MPESA_ENV["OAUTH_URL"],
        auth=(key, secret)
    )
    response.raise_for_status()
    return response.json().get("access_token")

def generate_stk_password():
    """Generate base64 password for STK Push"""
    shortcode = settings.MPESA_ENV["SHORTCODE"]
    passkey = settings.MPESA_ENV["PASSKEY"]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data_to_encode = shortcode + passkey + timestamp
    encoded_string = base64.b64encode(data_to_encode.encode()).decode("utf-8")
    return encoded_string, timestamp
