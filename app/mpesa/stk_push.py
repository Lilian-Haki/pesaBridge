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
    if getattr(settings, "MPESA_ENV", "sandbox") == "sandbox":
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
        print(f"✓ Access Token: {token[:20]}..." if token else "✗ No token")
        return token
    except Exception as e:
        print(f"✗ Failed to generate access token: {e}")
        return None


def lipa_na_mpesa_stk_push(phone, amount, account_reference, description):
    """
    Initiate M-Pesa STK Push using the provided phone number
    """

    print("\n" + "=" * 60)
    print("INITIATING M-PESA STK PUSH")
    print("=" * 60)

    # Step 1: Generate access token
    access_token = get_mpesa_access_token()
    if not access_token:
        return {"ResponseCode": "1", "errorMessage": "Failed to generate access token"}

    # Step 2: Format phone number
    phone = str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")

    # Convert to 254 format
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("7") or phone.startswith("1"):
        phone = "254" + phone
    elif not phone.startswith("254"):
        print(f"✗ Invalid phone format: {phone}")
        return {"ResponseCode": "1", "errorMessage": "Invalid phone number format"}

    # Validate phone length (should be 12 digits: 254XXXXXXXXX)
    if len(phone) != 12:
        print(f"✗ Invalid phone length: {phone} (should be 12 digits)")
        return {"ResponseCode": "1", "errorMessage": "Phone number must be 12 digits (254XXXXXXXXX)"}

    print(f"   Formatted Phone: {phone}")

    # Step 3: Prepare timestamp & password
    timestamp = generate_timestamp()

    # FIXED: Correct STK Push URLs
    if getattr(settings, "MPESA_ENV", "sandbox") == "sandbox":
        shortcode = "174379"  # Sandbox Paybill
        passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"  # Sandbox passkey
        stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        print("   Environment: SANDBOX")
    else:
        shortcode = settings.MPESA_SHORTCODE_PROD
        passkey = settings.MPESA_PASSKEY_PROD
        stk_push_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        print("   Environment: PRODUCTION")

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
    print(f"   STK URL: {stk_push_url}")  # Debug line

    # Step 4: Send request
    try:
        print(f"\nSending request to: {stk_push_url}")
        response = requests.post(stk_push_url, json=payload, headers=headers, timeout=30)

        # Print response for debugging
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")

        response.raise_for_status()
        json_response = response.json()

        if json_response.get("ResponseCode") == "0":
            print("✓ STK Push sent successfully!")
            print(f"   CheckoutRequestID: {json_response.get('CheckoutRequestID')}")
            print(f"   STK push sent to: {phone}")
        else:
            error_msg = json_response.get("errorMessage") or json_response.get("ResponseDescription") or "Unknown error"
            print(f"✗ STK Push failed: {error_msg}")

        print("=" * 60 + "\n")
        return json_response

    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP Error: {e}")
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text}")
        return {"ResponseCode": "1", "errorMessage": f"HTTP {response.status_code}: {response.text}"}

    except requests.exceptions.Timeout:
        print("✗ Error: Request timed out")
        return {"ResponseCode": "1", "errorMessage": "Request timeout"}

    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return {"ResponseCode": "1", "errorMessage": str(e)}

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {"ResponseCode": "1", "errorMessage": str(e)}