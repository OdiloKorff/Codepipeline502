
import requests

# VULNERABILITY: Hardcoded API Keys
OPENAI_API_KEY = "sk-1234567890abcdef1234567890abcdef1234567890abcdef12"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DATABASE_PASSWORD = "super_secret_password_123!"

# VULNERABILITY: Hardcoded tokens in config
CONFIG = {
    "api_token": "ghp_1234567890abcdef1234567890abcdef123456",
    "jwt_secret": "my-super-secret-jwt-key-that-should-not-be-hardcoded",
    "stripe_key": "sk_test_1234567890abcdef1234567890abcdef12345678"
}

def make_api_call():
    """VULNERABLE: Using hardcoded secrets"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "X-API-Key": "AIzaSyDdVgKwhZl-aNLqx4MIIZkMTj2F_1234567"  # Hardcoded Google API Key
    }
    
    return requests.get("https://api.example.com/data", headers=headers)
