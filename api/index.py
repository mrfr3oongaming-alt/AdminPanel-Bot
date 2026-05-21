import time
import requests
import json
import re
import os
from datetime import datetime, date, timedelta
from urllib.parse import quote_plus
from pathlib import Path
import sqlite3
import telebot
from telebot import types
import threading
import traceback
import random
import logging
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask import Flask, request, jsonify

# ======================
# 🖥️ إعدادات اللوحة (IVASMS)
# ======================

IVASMS_DASHBOARD = {
    "name": "iVasms",
    "type": "ivasms",
    "login_url": "https://ivas.tempnum.qzz.io/login",
    "base_url": "https://ivas.tempnum.qzz.io",
    "sms_api_endpoint": "https://ivas.tempnum.qzz.io/portal/sms/received/getsms",
    "username": "هنا ايميلك",
    "password": "هنا الباص",
    "session": requests.Session(),
    "is_logged_in": False,
    "cookies": None,
    "csrf_token": None,
    "last_check": None
}

# ======================
# 🔧 إعدادات عامة
# ======================
USERNAME = "3adhammohamed@gmail.com"
PASSWORD = "ytytyt3212"
BOT_TOKEN = "8837371310:AAEV6xQO0Bhsl0xMjDqTrq-1YWt1yTvnmVo"
CHAT_IDS = ["-1001234567890"]  # ايدي القروب
REFRESH_INTERVAL = 3
TIMEOUT = 100
MAX_RETRIES = 5
RETRY_DELAY = 5

SENT_MESSAGES_FILE = "sent_messages.json"

ADMIN_IDS = [7244261447]  # الايدي بتاعك
DB_PATH = "bot.db"
FORCE_SUB_CHANNEL = None
FORCE_SUB_ENABLED = False
BOT_ACTIVE = True

# ======================
# 🌍 رموز الدول (مختصرة عشان المساحة)
# ======================
COUNTRY_CODES = {
    "20": ("Egypt", "🇪🇬", "EG"),
    "44": ("United Kingdom", "🇬🇧", "UK"),
    "1": ("USA/Canada", "🇺🇸", "US"),
    "49": ("Germany", "🇩🇪", "DE"),
    "33": ("France", "🇫🇷", "FR"),
    "34": ("Spain", "🇪🇸", "ES"),
    "39": ("Italy", "🇮🇹", "IT"),
    "90": ("Turkey", "🇹🇷", "TR"),
    "91": ("India", "🇮🇳", "IN"),
    "92": ("Pakistan", "🇵🇰", "PK"),
    "212": ("Morocco", "🇲🇦", "MA"),
    "213": ("Algeria", "🇩🇿", "DZ"),
    "216": ("Tunisia", "🇹🇳", "TN"),
    "218": ("Libya", "🇱🇾", "LY"),
    "249": ("Sudan", "🇸🇩", "SD"),
    "966": ("Saudi Arabia", "🇸🇦", "SA"),
    "971": ("UAE", "🇦🇪", "AE"),
    "961": ("Lebanon", "🇱🇧", "LB"),
    "962": ("Jordan", "🇯🇴", "JO"),
    "964": ("Iraq", "🇮🇶", "IQ"),
    "965": ("Kuwait", "🇰🇼", "KW"),
    "974": ("Qatar", "🇶🇦", "QA"),
    "973": ("Bahrain", "🇧🇭", "BH"),
}

# ======================
# 🗄️ قاعدة البيانات
# ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            country_code TEXT,
            assigned_number TEXT,
            is_banned INTEGER DEFAULT 0,
            private_combo_country TEXT DEFAULT NULL,
            language TEXT DEFAULT 'ar'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS combos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_code TEXT,
            combo_index INTEGER DEFAULT 1,
            numbers TEXT,
            UNIQUE(country_code, combo_index)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS otp_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT,
            otp TEXT,
            full_message TEXT,
            timestamp TEXT,
            assigned_to INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS private_combos (
            user_id INTEGER,
            country_code TEXT,
            numbers TEXT,
            PRIMARY KEY (user_id, country_code)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS force_sub_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_url TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1
        )
    ''')
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('welcome_photo', '')")
    conn.commit()
    conn.close()

init_db()

# ======================
# 🤖 إنشاء البوت
# ======================
bot = telebot.TeleBot(BOT_TOKEN)

# ======================
# إنشاء تطبيق Flask
# ======================
app = Flask(__name__)

# ======================
# دوال مساعدة
# ======================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def save_user(user_id, username="", first_name="", last_name="", country_code=None, assigned_number=None, private_combo_country=None, language=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = get_user(user_id)
    if existing:
        if country_code is None:
            country_code = existing[4]
        if assigned_number is None:
            assigned_number = existing[5]
        if private_combo_country is None:
            private_combo_country = existing[7]
        if language is None:
            language = existing[8] if len(existing) > 8 else 'ar'
    else:
        if language is None:
            language = 'ar'
    
    c.execute("""
        REPLACE INTO users (user_id, username, first_name, last_name, country_code, assigned_number, is_banned, private_combo_country, language)
        VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT is_banned FROM users WHERE user_id=?), 0), ?, ?)
    """, (user_id, username, first_name, last_name, country_code, assigned_number, user_id, private_combo_country, language))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def is_banned(user_id):
    user = get_user(user_id)
    return user and user[6] == 1

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def get_combo(country_code, combo_index=1, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if user_id:
        c.execute("SELECT numbers FROM private_combos WHERE user_id=? AND country_code=?", (user_id, country_code))
        row = c.fetchone()
        if row:
            conn.close()
            return json.loads(row[0])
    c.execute("SELECT numbers FROM combos WHERE country_code=? AND combo_index=?", (country_code, combo_index))
    row = c.fetchone()
    conn.close()
    return json.loads(row[0]) if row else []

def save_combo(country_code, numbers, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if user_id:
        c.execute("REPLACE INTO private_combos (user_id, country_code, numbers) VALUES (?, ?, ?)",
                  (user_id, country_code, json.dumps(numbers)))
    else:
        c.execute("SELECT MAX(combo_index) FROM combos WHERE country_code=?", (country_code,))
        max_index = c.fetchone()[0]
        next_index = 1 if max_index is None else max_index + 1
        c.execute("INSERT INTO combos (country_code, combo_index, numbers) VALUES (?, ?, ?)",
                  (country_code, next_index, json.dumps(numbers)))
    conn.commit()
    conn.close()

def get_all_combos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT country_code, combo_index FROM combos ORDER BY country_code, combo_index")
    combos = c.fetchall()
    conn.close()
    return combos

def assign_number_to_user(user_id, number):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET assigned_number=? WHERE user_id=?", (number, user_id))
    conn.commit()
    conn.close()

def get_user_by_number(number):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE assigned_number=?", (number,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def release_number(old_number):
    if not old_number:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET assigned_number=NULL WHERE assigned_number=?", (old_number,))
    conn.commit()
    conn.close()

def log_otp(number, otp, full_message, assigned_to=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO otp_logs (number, otp, full_message, timestamp, assigned_to) VALUES (?, ?, ?, ?, ?)",
              (number, otp, full_message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), assigned_to))
    conn.commit()
    conn.close()

def clean_number(number):
    if not number:
        return ""
    return re.sub(r'\D', '', str(number))

def clean_html(text):
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', str(text))

def get_country_info(number):
    num = clean_number(number)
    for code, (name, flag, short) in COUNTRY_CODES.items():
        if num.startswith(code):
            return name, flag, short
    return "Unknown", "🌍", "UN"

def mask_number(number):
    num = str(number).strip()
    if len(num) > 8:
        return num[:4] + "••••" + num[-3:]
    return num

def extract_otp(message):
    patterns = [
        r'(?:code|رمز|كود|verification|otp|pin)[:\s]+[‎]?(\d{3,8}(?:[- ]\d{3,4})?)',
        r'(\d{3})[- ](\d{3,4})',
        r'\b(\d{4,8})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            if len(match.groups()) > 1:
                return ''.join(match.groups())
            return match.group(1).replace(' ', '').replace('-', '')
    all_numbers = re.findall(r'\d{4,8}', message)
    if all_numbers:
        return all_numbers[0]
    return "N/A"

def detect_service(message):
    message_lower = message.lower()
    services = {
        "WhatsApp": ["whatsapp", "واتساب"],
        "Telegram": ["telegram", "تيليجرام"],
        "Facebook": ["facebook", "فيسبوك"],
        "Instagram": ["instagram", "انستقرام"],
        "Google": ["google", "gmail", "جوجل"],
        "Twitter": ["twitter", "تويتر"],
    }
    for service, keywords in services.items():
        for keyword in keywords:
            if keyword in message_lower:
                return service
    return "Unknown"

def get_available_numbers(country_code, combo_index=1, user_id=None):
    all_numbers = get_combo(country_code, combo_index, user_id)
    if not all_numbers:
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT assigned_number FROM users WHERE assigned_number IS NOT NULL")
    used = set(row[0] for row in c.fetchall())
    conn.close()
    return [num for num in all_numbers if num not in used]

def login_to_ivasms():
    dash = IVASMS_DASHBOARD
    try:
        session = dash["session"]
        login_page = session.get(dash["login_url"], timeout=30)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        token_input = soup.find('input', {'name': '_token'})
        csrf = token_input['value'] if token_input else None
        
        login_data = {'email': dash["username"], 'password': dash["password"]}
        if csrf:
            login_data['_token'] = csrf
        
        resp = session.post(dash["login_url"], data=login_data, timeout=30)
        if "login" not in resp.url.lower():
            dash['is_logged_in'] = True
            dash['cookies'] = session.cookies.get_dict()
            print(f"[{dash['name']}] ✅ Login successful")
            return True
        return False
    except Exception as e:
        print(f"[!] Login error: {e}")
        return False

# ======================
# 🎮 أوامر البوت
# ======================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if is_banned(user_id):
        bot.reply_to(message, "🚫 You are banned!")
        return
    
    if not get_user(user_id):
        save_user(user_id, username=message.from_user.username or "", first_name=message.from_user.first_name or "")
    
    welcome_text = """✨ <b>Welcome to NumPulse Bot</b> ✨

🌟 Get free virtual numbers easily.
📱 Receive SMS verification codes

📊 Daily Limit: 3 numbers per user

👨‍💻 Developer: @ramosb"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📲 Get Free Number", callback_data="get_number"))
    
    if is_admin(user_id):
        markup.add(types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel"))
    
    bot.send_message(chat_id, welcome_text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "get_number")
def handle_get_number(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if is_banned(user_id):
        bot.answer_callback_query(call.id, "🚫 You are banned!", show_alert=True)
        return
    
    combos = get_all_combos()
    if not combos:
        bot.answer_callback_query(call.id, "❌ No numbers available!", show_alert=True)
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for code, idx in combos:
        if code in COUNTRY_CODES:
            name, flag, _ = COUNTRY_CODES[code]
            markup.add(types.InlineKeyboardButton(f"{flag} {name}", callback_data=f"select_{code}_{idx}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_menu"))
    bot.edit_message_text("🌍 Select country:", chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
def handle_country_select(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    parts = call.data.split("_")
    country_code = parts[1]
    combo_index = int(parts[2])
    
    numbers = get_available_numbers(country_code, combo_index, user_id)
    if not numbers:
        bot.answer_callback_query(call.id, "❌ No numbers available!", show_alert=True)
        return
    
    assigned = random.choice(numbers)
    old_user = get_user(user_id)
    if old_user and old_user[5]:
        release_number(old_user[5])
    
    assign_number_to_user(user_id, assigned)
    save_user(user_id, assigned_number=assigned)
    
    name, flag, _ = COUNTRY_CODES.get(country_code, ("Unknown", "🌍", ""))
    
    msg = f"""📱 Live SMS Inbox: +{assigned}

📍 Country: {flag} {name}
⏰ Waiting for SMS...

💡 Enter number in WhatsApp/Telegram"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{assigned}"))
    markup.add(types.InlineKeyboardButton("🔄 Change Number", callback_data="get_number"))
    markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_menu"))
    
    bot.edit_message_text(msg, chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("refresh_"))
def handle_refresh(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    number = call.data.split("_")[1]
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT otp, full_message FROM otp_logs WHERE number=? ORDER BY timestamp DESC LIMIT 1", (number,))
    row = c.fetchone()
    conn.close()
    
    if row:
        otp, msg = row
        service = detect_service(msg)
        
        code_text = f"""✅ Code received!

📱 +{number}
🔧 Service: {service}
📋 Code: <code>{otp}</code>"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Copy Code", callback_data=f"copy_{otp}"))
        markup.add(types.InlineKeyboardButton("🔄 Change Number", callback_data="get_number"))
        markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_menu"))
        
        bot.edit_message_text(code_text, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ No code yet! Please wait.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_"))
def handle_copy(call):
    code = call.data.split("_")[1]
    bot.answer_callback_query(call.id, f"✅ Copied: {code}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "back_menu")
def back_to_menu(call):
    send_welcome(call.message)

# ======================
# 🚀 Vercel Webhook endpoint
# ======================

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Bot is running!", "message": "Use /webhook endpoint"}), 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update_data = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(update_data)
        bot.process_new_updates([update])
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ======================
# تشغيل البوت
# ======================

# حذف webhook القديم وتعيين الجديد
def set_webhook():
    webhook_url = f"https://{os.environ.get('VERCEL_URL', 'localhost')}/{BOT_TOKEN}"
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": webhook_url}
    )
    print(f"Webhook set: {response.json()}")

# استدعاء تعيين webhook عند بدء التشغيل
set_webhook()
