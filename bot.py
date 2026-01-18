import os
import requests
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"

app = Flask(__name__)

def ask_ai(text):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bodoaisw.onrender.com",
        "X-Title": "Telegram OpenRouter Bot",
    }

    payload = {
        "model": "deepseek/deepseek-r1-0528:free",
        "messages": [
            {"role": "user", "content": text}
        ]
    }

    r = requests.post(OPENROUTER_API, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text:
            try:
                reply = ask_ai(text)
            except Exception:
                reply = "⚠️ AI error. Try again later."

            send_message(chat_id, reply)

    return "OK", 200

@app.route("/")
def home():
    return "🤖 Telegram Bot Running (Docker)"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
