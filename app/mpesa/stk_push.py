# app/mpesa/stk_push.py

import requests
from django.conf import settings
from app.mpesa.utils import generate_stk_password, generate_timestamp


def get_mpesa_access_token():
    """
    Generate a fresh M-Pesa access token
    """
    import base64

    # Determine environment
    if getattr(settings, "MPESA_ENV","sandbox") == "sandbox":
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    else:
        consumer_key = settings.MPESA_CONSUMER_KEY_PROD
        consumer_secret = settings.MPESA_CONSUMER_SECRET_PROD
        url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    auth = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        token = response.json().get("access_token")
        print(f"✓ Access Token: {token}")
        return token
    except Exception as e:
        print(f"✗ Failed to generate access token: {e}")
        return None


def lipa_na_mpesa_stk_push(phone, amount, account_reference, description):
    """
    Initiate M-Pesa STK Push
    """

    print("\n" + "=" * 60)
    print("INITIATING M-PESA STK PUSH")
    print("=" * 60)

    # Step 1: Generate access token
    access_token = get_mpesa_access_token()
    if not access_token:
        return {"ResponseCode": "1", "errorMessage": "Failed to generate access token"}

    # Step 2: Prepare timestamp & password
    timestamp = generate_timestamp()

    # Use sandbox Paybill and test number if in sandbox mode
    if getattr(settings, "MPESA_ENV", "sandbox") == "sandbox":
        shortcode = "174379"  # Default sandbox Paybill
        passkey = settings.MPESA_PASSKEY
        stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    else:
        shortcode = settings.MPESA_SHORTCODE_PROD
        passkey = settings.MPESA_PASSKEY_PROD
        stk_push_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    password = generate_stk_password(shortcode, passkey, timestamp)

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

    print(f"   Phone: {phone}")
    print(f"   Amount: KES {amount}")
    print(f"   Reference: {account_reference}")
    print(f"   Shortcode: {shortcode}")
    print(f"   Callback: {settings.MPESA_CALLBACK_URL}")

    # Step 3: Send request
    try:
        response = requests.post(stk_push_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        json_response = response.json()

        if json_response.get("ResponseCode") == "0":
            print("✓ STK Push sent successfully!")
            print(f"   CheckoutRequestID: {json_response.get('CheckoutRequestID')}")
        else:
            error_msg = json_response.get("errorMessage") or json_response.get("ResponseDescription") or "Unknown error"
            print(f"✗ STK Push failed: {error_msg}")

        print("=" * 60 + "\n")
        return json_response

    except requests.exceptions.Timeout:
        print("✗ Error: Request timed out")
        return {"ResponseCode": "1", "errorMessage": "Request timeout"}

    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return {"ResponseCode": "1", "errorMessage": str(e)}

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return {"ResponseCode": "1", "errorMessage": str(e)}
