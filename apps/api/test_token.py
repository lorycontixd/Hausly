import firebase_admin
from firebase_admin import auth, credentials

cred = credentials.Certificate("./firebase-sa.json")
app = firebase_admin.initialize_app(cred)

token = input("Paste your idToken: ").strip()

try:
    decoded = auth.verify_id_token(token)
    print(f"Success! UID: {decoded['uid']}, Email: {decoded.get('email')}")
except Exception as e:
    print(f"Error type: {type(e).__name__}")
    print(f"Error: {e}")