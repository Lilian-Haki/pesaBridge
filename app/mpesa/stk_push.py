import requests
import base64
from django.conf import settings
from datetime import datetime

def generate_access_token():
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    auth = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()

    headers = {"Authorization": f"Basic {auth}"}
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    r = requests.get(url, headers=headers)
    return r.json().get("access_token")


def lipa_na_mpesa_stk_push(phone, amount, account_reference, description):
    access_token = generate_access_token()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY

    data_to_encode = shortcode + passkey + timestamp
    password = base64.b64encode(data_to_encode.encode()).decode()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": description
    }

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    response = requests.post(url, json=payload, headers=headers)

    try:
        return response.json()
    except:
        return {"ResponseCode": "1", "error": "Invalid JSON returned"}
