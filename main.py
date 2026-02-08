from flask import Flask, render_template, request, jsonify
from pyrogram import Client
import asyncio
import os
from functools import partial

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Temporary Storage for Sessions (Vercel memory me rahega thodi der ke liye)
TEMP_CLIENTS = {}

def get_client(phone):
    """Helper to get or create client"""
    return TEMP_CLIENTS.get(phone)

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html", step="login")

@app.route("/send_otp", methods=["POST"])
def send_otp():
    data = request.json
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    phone = data.get("phone")

    # Naya Client Banao
    client = Client(f"session_{phone}", api_id=api_id, api_hash=api_hash, in_memory=True)
    TEMP_CLIENTS[phone] = client

    async def connect_and_send():
        await client.connect()
        try:
            sent = await client.send_code(phone)
            return sent.phone_code_hash
        except Exception as e:
            await client.disconnect()
            raise e

    try:
        # Async loop chalao
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        phone_code_hash = loop.run_until_complete(connect_and_send())
        return jsonify({"status": "success", "phone_code_hash": phone_code_hash})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.json
    phone = data.get("phone")
    code = data.get("code")
    phone_code_hash = data.get("phone_code_hash")
    
    client = get_client(phone)
    if not client:
        return jsonify({"status": "error", "message": "Session expired. Reload page."})

    async def sign_in_user():
        try:
            await client.sign_in(phone, phone_code_hash, code)
            string_session = await client.export_session_string()
            await client.disconnect()
            # Clean up
            del TEMP_CLIENTS[phone]
            return string_session
        except Exception as e:
            # Agar 2FA laga ho
            if "SESSION_PASSWORD_NEEDED" in str(e):
                return "2FA_REQUIRED"
            raise e

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(sign_in_user())
        
        if result == "2FA_REQUIRED":
            return jsonify({"status": "2fa_required"})
        
        return jsonify({"status": "success", "string_session": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/verify_2fa", methods=["POST"])
def verify_2fa():
    data = request.json
    phone = data.get("phone")
    password = data.get("password")
    
    client = get_client(phone)
    if not client:
        return jsonify({"status": "error", "message": "Session expired."})

    async def check_password():
        try:
            await client.check_password(password=password)
            string_session = await client.export_session_string()
            await client.disconnect()
            del TEMP_CLIENTS[phone]
            return string_session
        except Exception as e:
            raise e

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(check_password())
        return jsonify({"status": "success", "string_session": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(debug=True)
  
