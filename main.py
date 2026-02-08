from flask import Flask, render_template, request, jsonify
from pyrogram import Client
import asyncio
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Hum sirf credentials save karenge, Client object nahi (to avoid Loop error)
TEMP_DATA = {}

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html", step="login")

@app.route("/send_otp", methods=["POST"])
def send_otp():
    data = request.json
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")
    phone = data.get("phone")

    # Credentials save kar lo agle step ke liye
    TEMP_DATA[phone] = {"api_id": api_id, "api_hash": api_hash}

    async def run_client():
        # Temporary client sirf Hash lene ke liye
        client = Client(f"session_{phone}", api_id=api_id, api_hash=api_hash, in_memory=True)
        await client.connect()
        try:
            sent = await client.send_code(phone)
            return sent.phone_code_hash
        except Exception as e:
            raise e
        finally:
            await client.disconnect()

    try:
        # Naya loop har request ke liye
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        phone_code_hash = loop.run_until_complete(run_client())
        loop.close()
        
        return jsonify({"status": "success", "phone_code_hash": phone_code_hash})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    data = request.json
    phone = data.get("phone")
    code = data.get("code")
    phone_code_hash = data.get("phone_code_hash")

    # Credentials wapas nikalo
    creds = TEMP_DATA.get(phone)
    if not creds:
        return jsonify({"status": "error", "message": "Session expired. Please reload."})

    async def run_client():
        # Naya Client banao Verify karne ke liye
        client = Client(f"session_{phone}", api_id=creds['api_id'], api_hash=creds['api_hash'], in_memory=True)
        await client.connect()
        try:
            await client.sign_in(phone, phone_code_hash, code)
            string_session = await client.export_session_string()
            return string_session
        except Exception as e:
            if "SESSION_PASSWORD_NEEDED" in str(e):
                return "2FA_REQUIRED"
            raise e
        finally:
            await client.disconnect()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_client())
        loop.close()

        if result == "2FA_REQUIRED":
            return jsonify({"status": "2fa_required"})
        
        # Kaam ho gaya, data clear kar do
        if phone in TEMP_DATA:
            del TEMP_DATA[phone]
            
        return jsonify({"status": "success", "string_session": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/verify_2fa", methods=["POST"])
def verify_2fa():
    data = request.json
    phone = data.get("phone")
    password = data.get("password")
    
    # Is step pe humein phone_code_hash ki zarurat nahi hoti usually, 
    # bas connected client chahiye. Lekin stateless environment mein humein 
    # login flow resume karna padta hai.
    # NOTE: Pyrogram stateless 2FA support thoda tricky hai bina session file ke.
    # Lekin hum try karte hain login flow recreate karne ka.
    
    creds = TEMP_DATA.get(phone)
    if not creds:
        return jsonify({"status": "error", "message": "Session expired."})

    # Note: Asliyat mein 2FA ke liye pichla 'Client' object connected hona chahiye tha.
    # Kyunki hum naya client bana rahe hain, humein wapas sign_in try karna padega
    # lekin bina OTP ke wo fail hoga. 
    # Vercel par 2FA handle karna bina database ke mushkil hai.
    
    # Filhal ke liye simple error return karte hain agar 2FA laga hai
    return jsonify({"status": "error", "message": "2FA is not supported on Vercel (Stateless Mode). Turn off 2FA temporarily."})

if __name__ == "__main__":
    app.run(debug=True)
    
