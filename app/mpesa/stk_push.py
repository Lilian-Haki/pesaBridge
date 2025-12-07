# app/mpesa/stk_push.py

import requests
from django.conf import settings
from app.mpesa.utils import get_mpesa_access_token, generate_stk_password, generate_timestamp


def lipa_na_mpesa_stk_push(phone, amount, account_reference, description):
    """
    Initiate M-Pesa STK Push to customer's phone

    Args:
        phone (str): Customer phone number in format 254XXXXXXXXX
        amount (int/float): Amount to charge
        account_reference (str): Reference for the transaction (e.g., "Loan-123")
        description (str): Transaction description

    Returns:
        dict: M-Pesa API response
    """
    print("\n" + "=" * 60)
    print("INITIATING M-PESA STK PUSH")
    print("=" * 60)

    # Step 1: Get access token
    print("Step 1: Getting access token...")
    access_token = get_mpesa_access_token()

    if not access_token:
        error_response = {
            "ResponseCode": "1",
            "errorMessage": "Failed to generate access token. Check your credentials."
        }
        print(f"✗ Error: {error_response['errorMessage']}")
        return error_response

    print("✓ Access token obtained")

    # Step 2: Generate timestamp and password
    print("Step 2: Generating password...")
    timestamp = generate_timestamp()
    password = generate_stk_password(
        settings.MPESA_SHORTCODE,
        settings.MPESA_PASSKEY,
        timestamp
    )
    print(f"✓ Password generated for timestamp: {timestamp}")

    # Step 3: Prepare API request
    print("Step 3: Preparing STK Push request...")
    api_url = settings.MPESA_STK_PUSH_URL

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": description
    }

    print(f"   Phone: {phone}")
    print(f"   Amount: KES {amount}")
    print(f"   Reference: {account_reference}")
    print(f"   Shortcode: {settings.MPESA_SHORTCODE}")
    print(f"   Callback: {settings.MPESA_CALLBACK_URL}")

    # Step 4: Send request to M-Pesa
    print("Step 4: Sending request to M-Pesa...")
    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=30
        )

        json_response = response.json()

        print(f"   Status Code: {response.status_code}")
        print(f"   Response Code: {json_response.get('ResponseCode', 'N/A')}")
        print(f"   Response Description: {json_response.get('ResponseDescription', 'N/A')}")

        if json_response.get('ResponseCode') == '0':
            print("✓ STK Push sent successfully!")
            print(f"   CheckoutRequestID: {json_response.get('CheckoutRequestID', 'N/A')}")
        else:
            print(f"✗ STK Push failed: {json_response.get('errorMessage', 'Unknown error')}")

        print("=" * 60 + "\n")
        return json_response

    except requests.exceptions.Timeout:
        error_response = {
            "ResponseCode": "1",
            "errorMessage": "Request timeout. Please try again."
        }
        print(f"✗ Error: Timeout")
        print("=" * 60 + "\n")
        return error_response

    except requests.exceptions.RequestException as e:
        error_response = {
            "ResponseCode": "1",
            "errorMessage": f"Request failed: {str(e)}"
        }
        print(f"✗ Error: {e}")
        print("=" * 60 + "\n")
        return error_response

    except Exception as e:
        error_response = {
            "ResponseCode": "1",
            "errorMessage": f"Unexpected error: {str(e)}"
        }
        print(f"✗ Unexpected error: {e}")
        print("=" * 60 + "\n")
        return error_response