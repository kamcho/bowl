import base64
from datetime import datetime
import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth

class MpesaService:
    @staticmethod
    def get_access_token():
        consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
        consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
        api_url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        
        try:
            r = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret), timeout=30)
            r.raise_for_status()
            token = r.json()['access_token']
            print(f"Mpesa Auth Success: Token acquired")
            return token
        except Exception as e:
            print(f"Mpesa Auth Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Mpesa Auth Error Response: {e.response.text}")
            return None

    @staticmethod
    def generate_password(shortcode, passkey):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_str = f"{shortcode}{passkey}{timestamp}"
        password_bytes = password_str.encode('ascii')
        return base64.b64encode(password_bytes).decode('utf-8'), timestamp

    @classmethod
    def stk_push(cls, phone_number, amount, account_reference):
        access_token = cls.get_access_token()
        if not access_token:
            return None, "Authentication failed"
            
        shortcode = getattr(settings, 'MPESA_SHORTCODE', '174379')
        passkey = getattr(settings, 'MPESA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
        callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
        
        password, timestamp = cls.generate_password(shortcode, passkey)
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Ensure phone number is in 254 format
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+'):
            phone_number = phone_number[1:]
            
        request_body = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": str(account_reference),
            "TransactionDesc": f"Enrollment for participation {account_reference}"
        }
        
        api_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        print(f"Initiating Mpesa STK Push for {phone_number} amount {amount}")
        
        try:
            r = requests.post(api_url, json=request_body, headers=headers, timeout=30)
            print(f"Mpesa STK Push Response Status: {r.status_code}")
            res_json = r.json()
            print(f"Mpesa STK Push Response Body: {res_json}")
            return res_json, None
        except Exception as e:
            print(f"Mpesa STK Push Exception: {e}")
            return None, str(e)
