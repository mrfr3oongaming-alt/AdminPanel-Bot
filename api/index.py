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
from flask import Flask, request, jsonify, render_template, redirect, session
from functools import wraps

# ======================
# 🔧 الإعدادات الرئيسية (بياناتك الأصلية)
# ======================

BOT_TOKEN = "8837371310:AAEV6xQO0Bhsl0xMjDqTrq-1YWt1yTvnmVo"
ADMIN_IDS = [7244261447]
CHAT_IDS = ["-1003957679217"]

BOT_GROUP_LINK = "https://t.me/NumPlus0TP"
BOT_OWNER_USERNAME = "@jq_b4"

# إعدادات iVasms Dashboard
IVASMS_DASHBOARD = {
    "name": "iVasms",
    "type": "ivasms",
    "login_url": "https://ivas.tempnum.qzz.io/login",
    "base_url": "https://ivas.tempnum.qzz.io",
    "sms_api_endpoint": "https://ivas.tempnum.qzz.io/portal/sms/received/getsms",
    "username": "3adhammohamed@gmail.com",
    "password": "ytytyt3212",
    "session": requests.Session(),
    "is_logged_in": False,
    "cookies": None,
    "csrf_token": None,
    "last_check": None
}

# إعدادات عامة
REFRESH_INTERVAL = 3
SENT_MESSAGES_FILE = "sent_messages.json"
DB_PATH = "bot.db"

# ======================
# 🌍 رموز الدول
# ======================
COUNTRY_CODES = {
    "20": ("Egypt", "🇪🇬", "EG"),
    "44": ("United Kingdom", "🇬🇧", "UK"),
    "1": ("USA/Canada", "🇺🇸", "US"),
    "49": ("Germany", "🇩🇪", "DE"),
    "33": ("France", "🇫🇷", "FR"),
    "34": ("Spain", "🇪🇸", "ES"),
    "39": ("Italy", "🇮🇹", "IT"),
    "7": ("Russia", "🇷🇺", "RU"),
    "90": ("Turkey", "🇹🇷", "TR"),
    "966": ("Saudi Arabia", "🇸🇦", "SA"),
    "971": ("UAE", "🇦🇪", "AE"),
    "962": ("Jordan", "🇯🇴", "JO"),
    "964": ("Iraq", "🇮🇶", "IQ"),
    "965": ("Kuwait", "🇰🇼", "KW"),
    "974": ("Qatar", "🇶🇦", "QA"),
    "212": ("Morocco", "🇲🇦", "MA"),
    "213": ("Algeria", "🇩🇿", "DZ"),
    "216": ("Tunisia", "🇹🇳", "TN"),
    "218": ("Libya", "🇱🇾", "LY"),
    "249": ("Sudan", "🇸🇩", "SD"),
    "254": ("Kenya", "🇰🇪", "KE"),
    "234": ("Nigeria", "🇳🇬", "NG"),
    "91": ("India", "🇮🇳", "IN"),
    "92": ("Pakistan", "🇵🇰", "PK"),
    "60": ("Malaysia", "🇲🇾", "MY"),
    "62": ("Indonesia", "🇮🇩", "ID"),
    "63": ("Philippines", "🇵🇭", "PH"),
    "81": ("Japan", "🇯🇵", "JP"),
    "82": ("South Korea", "🇰🇷", "KR"),
    "86": ("China", "🇨🇳", "CN"),
}

# ======================
# 🗄️ إنشاء تطبيق Flask
# ======================
app = Flask(__name__)
app.secret_key = "supersecretkey_123456789"

# ======================
# 🗄️ قاعدة البيانات (SQLite)
# ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        country_code TEXT,
        assigned_number TEXT,
        is_banned INTEGER DEFAULT 0,
        private_combo_country TEXT DEFAULT NULL,
        language TEXT DEFAULT 'ar',
        api_key TEXT DEFAULT NULL,
        created_at TEXT DEFAULT NULL
    )''')
    
    # جدول الكومبوهات (الأرقام)
    c.execute('''CREATE TABLE IF NOT EXISTS combos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country_code TEXT,
        combo_index INTEGER DEFAULT 1,
        numbers TEXT,
        UNIQUE(country_code, combo_index)
    )''')
    
    # جدول سجل الأكواد (OTP Logs)
    c.execute('''CREATE TABLE IF NOT EXISTS otp_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT,
        otp TEXT,
        full_message TEXT,
        service TEXT,
        timestamp TEXT,
        assigned_to INTEGER
    )''')
    
    # جدول الإعدادات
    c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # جدول الكومبوهات الخاصة
    c.execute('''CREATE TABLE IF NOT EXISTS private_combos (
        user_id INTEGER,
        country_code TEXT,
        numbers TEXT,
        PRIMARY KEY (user_id, country_code)
    )''')
    
    # جدول قنوات الاشتراك الإجباري
    c.execute('''CREATE TABLE IF NOT EXISTS force_sub_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_url TEXT UNIQUE NOT NULL,
        description TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1
    )''')
    
    # جدول مستخدمي الويب (لللوحة)
    c.execute('''CREATE TABLE IF NOT EXISTS web_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT DEFAULT NULL
    )''')
    
    # إضافة مستخدم أدمن افتراضي للويب (password: admin123)
    c.execute("INSERT OR IGNORE INTO web_users (username, password, is_admin, created_at) VALUES ('admin', 'admin123', 1, ?)", 
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    
    # إعدادات افتراضية
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('welcome_photo', '')")
    c.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('maintenance', '0')")
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

init_db()

# ======================
# 🤖 إنشاء بوت تيليجرام
# ======================
bot = telebot.TeleBot(BOT_TOKEN)

# ======================
# 🔐 دوال المصادقة للويب
# ======================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session.get('is_admin'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# ======================
# 🗄️ دوال قاعدة البيانات الأساسية
# ======================
def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def save_user(user_id, username="", first_name="", last_name="", country_code=None, assigned_number=None, private_combo_country=None, language='ar'):
    existing = get_user(user_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if existing:
        c.execute("""UPDATE users SET username=?, first_name=?, last_name=?, 
                     country_code=COALESCE(?,country_code), assigned_number=COALESCE(?,assigned_number), 
                     private_combo_country=COALESCE(?,private_combo_country), language=COALESCE(?,language)
                     WHERE user_id=?""",
                  (username, first_name, last_name, country_code, assigned_number, private_combo_country, language, user_id))
    else:
        c.execute("""INSERT INTO users (user_id, username, first_name, last_name, country_code, assigned_number, 
                     private_combo_country, language, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                  (user_id, username, first_name, last_name, country_code, assigned_number, private_combo_country, language,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def ban_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id):
    user = get_user(user_id)
    return user and user[6] == 1

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, last_name, created_at FROM users WHERE is_banned=0")
    users = c.fetchall()
    conn.close()
    return users

def get_all_banned_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, last_name FROM users WHERE is_banned=1")
    users = c.fetchall()
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

def save_combo(country_code, numbers, user_id=None, combo_index=1):
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

def delete_combo(country_code, combo_index=None, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if user_id:
        c.execute("DELETE FROM private_combos WHERE user_id=? AND country_code=?", (user_id, country_code))
    elif combo_index:
        c.execute("DELETE FROM combos WHERE country_code=? AND combo_index=?", (country_code, combo_index))
    else:
        c.execute("DELETE FROM combos WHERE country_code=?", (country_code,))
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

def log_otp(number, otp, full_message, service, assigned_to=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO otp_logs (number, otp, full_message, service, timestamp, assigned_to) 
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (number, otp, full_message, service, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), assigned_to))
    conn.commit()
    conn.close()

def get_otp_logs(limit=50, number=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if number:
        c.execute("SELECT * FROM otp_logs WHERE number=? ORDER BY timestamp DESC LIMIT ?", (number, limit))
    else:
        c.execute("SELECT * FROM otp_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    logs = c.fetchall()
    conn.close()
    return logs

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

def get_available_numbers(country_code, combo_index=1, user_id=None):
    all_numbers = get_combo(country_code, combo_index, user_id)
    if not all_numbers:
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT assigned_number FROM users WHERE assigned_number IS NOT NULL AND assigned_number != ''")
    used_numbers = set(row[0] for row in c.fetchall())
    conn.close()
    return [num for num in all_numbers if num not in used_numbers]

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM otp_logs")
    total_otps = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE assigned_number IS NOT NULL")
    active_numbers = c.fetchone()[0]
    conn.close()
    return {
        'total_users': total_users,
        'banned_users': banned_users,
        'total_otps': total_otps,
        'active_numbers': active_numbers
    }

# ======================
# 🧹 دوال مساعدة
# ======================
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
    # تجربة المفاتيح الأطول أولاً
    sorted_codes = sorted(COUNTRY_CODES.keys(), key=len, reverse=True)
    for code in sorted_codes:
        if num.startswith(code):
            name, flag, short = COUNTRY_CODES[code]
            return name, flag, short
    return "Unknown", "🌍", "UN"

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
        "WhatsApp": ["whatsapp", "واتساب", "واتس"],
        "Telegram": ["telegram", "تيليجرام", "تلي"],
        "Facebook": ["facebook", "فيسبوك", "fb"],
        "Instagram": ["instagram", "انستقرام", "انستا"],
        "Google": ["google", "gmail", "جوجل"],
        "Twitter": ["twitter", "تويتر"],
        "TikTok": ["tiktok", "تيك توك"],
        "Snapchat": ["snapchat", "سناب"],
        "Microsoft": ["microsoft", "مايكروسوفت", "outlook"],
        "Apple": ["apple", "ابل", "icloud"],
        "Amazon": ["amazon", "امازون"],
        "PayPal": ["paypal", "باي بال"],
        "Netflix": ["netflix", "نتفلكس"],
        "Spotify": ["spotify", "سبوتيفاي"],
        "Discord": ["discord", "ديسكورد"],
        "Uber": ["uber", "اوبر"],
        "LinkedIn": ["linkedin", "لينكد"],
    }
    for service, keywords in services.items():
        for keyword in keywords:
            if keyword in message_lower:
                return service
    return "Unknown"

def login_to_ivasms():
    """تسجيل الدخول إلى لوحة iVasms"""
    dash = IVASMS_DASHBOARD
    try:
        session = dash["session"]
        login_url = dash["login_url"]
        
        # جلب صفحة الدخول لاستخراج CSRF token
        login_page = session.get(login_url, timeout=30)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        token_input = soup.find('input', {'name': '_token'})
        csrf = token_input['value'] if token_input else None
        
        login_data = {
            'email': dash["username"],
            'password': dash["password"]
        }
        if csrf:
            login_data['_token'] = csrf
        
        resp = session.post(login_url, data=login_data, timeout=30)
        
        if "login" not in resp.url.lower():
            dash['is_logged_in'] = True
            dash['cookies'] = session.cookies.get_dict()
            print(f"[{dash['name']}] ✅ Login successful")
            return True
        else:
            print(f"[{dash['name']}] ❌ Login failed")
            return False
    except Exception as e:
        print(f"[!] Login error: {e}")
        return False

def fetch_ivasms_messages():
    """جلب الرسائل من iVasms"""
    dash = IVASMS_DASHBOARD
    
    if not dash.get('is_logged_in'):
        if not login_to_ivasms():
            return []
    
    try:
        session = dash['session']
        api_url = dash['sms_api_endpoint']
        
        # جلب آخر 24 ساعة
        today = datetime.utcnow()
        start_date = (today - timedelta(days=1)).strftime('%m/%d/%Y')
        end_date = today.strftime('%m/%d/%Y')
        
        # إعداد الهيدرز
        headers = {
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        payload = {
            'from': start_date,
            'to': end_date
        }
        
        resp = session.post(api_url, headers=headers, data=payload, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        all_messages = []
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:
                date_cell = cells[0].text.strip() if len(cells) > 0 else ""
                number_cell = cells[2].text.strip() if len(cells) > 2 else ""
                sms_cell = cells[5].text.strip() if len(cells) > 5 else ""
                
                if number_cell and sms_cell:
                    all_messages.append({
                        'date': date_cell,
                        'number': clean_number(number_cell),
                        'sms': clean_html(sms_cell)
                    })
        
        return all_messages
    except Exception as e:
        print(f"[!] Fetch error: {e}")
        if "401" in str(e):
            dash['is_logged_in'] = False
        return []

# ======================
# 📱 أوامر بوت تيليجرام
# ======================

def is_admin(user_id):
    return user_id in ADMIN_IDS

def main_menu_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📲 Get Number", callback_data="get_number"))
    markup.add(types.InlineKeyboardButton("ℹ️ Info", callback_data="info"))
    if is_admin(user_id):
        markup.add(types.InlineKeyboardButton("🔐 Admin Panel", callback_data="admin_panel"))
    markup.add(types.InlineKeyboardButton("👥 Our Channel", url=BOT_GROUP_LINK))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if is_banned(user_id):
        bot.reply_to(message, "🚫 You are banned from using this bot.")
        return
    
    if not get_user(user_id):
        save_user(
            user_id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name or ""
        )
    
    welcome_text = f"""✨ <b>Welcome to NumPulse Bot</b> ✨

🌟 Get free virtual numbers easily.
📱 Receive SMS verification codes

📊 Daily Limit: 3 numbers per user

👨‍💻 Owner: {BOT_OWNER_USERNAME}
📢 Channel: <a href='{BOT_GROUP_LINK}'>NumPlus0TP</a>

<b>Click the button below to start!</b>"""
    
    welcome_photo = get_setting("welcome_photo")
    if welcome_photo:
        try:
            bot.send_photo(chat_id, welcome_photo, caption=welcome_text, 
                          parse_mode="HTML", reply_markup=main_menu_keyboard(user_id))
        except:
            bot.send_message(chat_id, welcome_text, parse_mode="HTML", 
                           reply_markup=main_menu_keyboard(user_id))
    else:
        bot.send_message(chat_id, welcome_text, parse_mode="HTML", 
                        reply_markup=main_menu_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "info")
def handle_info(call):
    user_id = call.from_user.id
    info_text = f"""ℹ️ <b>About NumPulse</b>

🔹 <b>Service</b>: Free temporary virtual numbers
🔹 <b>Daily Limit</b>: 3 numbers per user
🔹 <b>Supported Services</b>: WhatsApp, Telegram, Instagram, Facebook, Google, Twitter, TikTok, and more

<b>How to use:</b>
1️⃣ Select a country
2️⃣ Get a virtual number
3️⃣ Use it for verification
4️⃣ Wait for SMS
5️⃣ Copy the code

👨‍💻 <b>Developer</b>: {BOT_OWNER_USERNAME}
📢 <b>Channel</b>: <a href='{BOT_GROUP_LINK}'>NumPlus0TP</a>"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_menu"))
    bot.edit_message_text(info_text, call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "get_number")
def handle_get_number(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if is_banned(user_id):
        bot.answer_callback_query(call.id, "🚫 You are banned!", show_alert=True)
        return
    
    combos = get_all_combos()
    if not combos:
        bot.answer_callback_query(call.id, "❌ No numbers available! Contact admin.", show_alert=True)
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for code, idx in combos:
        if code in COUNTRY_CODES:
            name, flag, _ = COUNTRY_CODES[code]
            btn_text = f"{flag} {name}"
            if idx > 1:
                btn_text += f" #{idx}"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"select_{code}_{idx}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_menu"))
    bot.edit_message_text("🌍 <b>Select your country:</b>", chat_id, call.message.message_id,
                         parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
def handle_country_select(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    parts = call.data.split("_")
    country_code = parts[1]
    combo_index = int(parts[2]) if len(parts) > 2 else 1
    
    available = get_available_numbers(country_code, combo_index, user_id)
    if not available:
        bot.answer_callback_query(call.id, "❌ No numbers available for this country!", show_alert=True)
        return
    
    assigned = random.choice(available)
    old_user = get_user(user_id)
    if old_user and old_user[5]:
        release_number(old_user[5])
    
    assign_number_to_user(user_id, assigned)
    save_user(user_id, assigned_number=assigned)
    
    name, flag, _ = COUNTRY_CODES.get(country_code, ("Unknown", "🌍", ""))
    
    msg = f"""📱 <b>Live SMS Inbox</b>

🔢 <b>Number:</b> <code>+{assigned}</code>
📍 <b>Country:</b> {flag} {name}
🔄 <b>Combo:</b> #{combo_index}

⏳ <b>Status:</b> Waiting for SMS...

💡 <i>Enter the number in WhatsApp/Telegram, then click Refresh</i>"""
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{assigned}"),
        types.InlineKeyboardButton("📋 Copy Number", callback_data=f"copy_num_{assigned}")
    )
    markup.row(
        types.InlineKeyboardButton("🔄 Change Number", callback_data="get_number"),
        types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_menu")
    )
    
    bot.edit_message_text(msg, chat_id, call.message.message_id,
                         parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("refresh_"))
def handle_refresh(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    number = call.data.split("_")[1]
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT otp, service, full_message, timestamp FROM otp_logs WHERE number=? ORDER BY timestamp DESC LIMIT 1", (number,))
    row = c.fetchone()
    conn.close()
    
    if row:
        otp, service, full_msg, timestamp = row
        service_emoji = "💬"
        
        msg = f"""✅ <b>Code Received!</b>

🔢 <b>Number:</b> <code>+{number}</code>
🔧 <b>Service:</b> {service_emoji} {service}
⏰ <b>Time:</b> {timestamp}
📋 <b>Code:</b> <code>{otp}</code>

💡 <i>Click Copy to use the code</i>"""
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Copy Code", callback_data=f"copy_{otp}"))
        markup.row(
            types.InlineKeyboardButton("🔄 Refresh Again", callback_data=f"refresh_{number}"),
            types.InlineKeyboardButton("🔄 Change Number", callback_data="get_number")
        )
        markup.add(types.InlineKeyboardButton("🏠 Main Menu", callback_data="back_menu"))
        
        bot.edit_message_text(msg, chat_id, call.message.message_id,
                             parse_mode="HTML", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ No code received yet! Please wait.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_"))
def handle_copy_code(call):
    code = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, f"✅ Code copied: {code}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_num_"))
def handle_copy_number(call):
    number = call.data.split("_")[2]
    bot.answer_callback_query(call.id, f"✅ Number copied: +{number}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "back_menu")
def back_to_menu(call):
    user_id = call.from_user.id
    welcome_text = f"""✨ <b>Welcome to NumPulse Bot</b> ✨

🌟 Get free virtual numbers easily.
📱 Receive SMS verification codes

👨‍💻 Owner: {BOT_OWNER_USERNAME}
📢 Channel: <a href='{BOT_GROUP_LINK}'>NumPlus0TP</a>"""
    
    bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=main_menu_keyboard(user_id))

# ======================
# 🔐 Admin Panel Callbacks (Telegam)
# ======================

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
        return
    
    stats = get_stats()
    admin_text = f"""🔐 <b>Admin Control Panel</b>

📊 <b>Statistics:</b>
• Total Users: {stats['total_users']}
• Banned Users: {stats['banned_users']}
• Active Users: {stats['total_users'] - stats['banned_users']}
• Total OTPs: {stats['total_otps']}
• Active Numbers: {stats['active_numbers']}

⚙️ <b>Quick Actions:</b>"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"))
    markup.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"))
    markup.add(types.InlineKeyboardButton("➕ Add Combo", callback_data="admin_add_combo"))
    markup.add(types.InlineKeyboardButton("🗑️ Delete Combo", callback_data="admin_del_combo"))
    markup.add(types.InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban"))
    markup.add(types.InlineKeyboardButton("✅ Unban User", callback_data="admin_unban"))
    markup.add(types.InlineKeyboardButton("👤 User Info", callback_data="admin_user_info"))
    markup.add(types.InlineKeyboardButton("🖼️ Set Welcome Photo", callback_data="admin_set_photo"))
    markup.add(types.InlineKeyboardButton("🔗 Dashboard URL", callback_data="admin_dashboard_url"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_menu"))
    
    bot.edit_message_text(admin_text, call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats(call):
    if not is_admin(call.from_user.id):
        return
    stats = get_stats()
    stats_text = f"""📊 <b>Detailed Statistics</b>

👥 <b>Users:</b>
├ Total: {stats['total_users']}
├ Active: {stats['total_users'] - stats['banned_users']}
└ Banned: {stats['banned_users']}

📱 <b>Numbers & OTPs:</b>
├ Active Numbers: {stats['active_numbers']}
└ Total OTPs: {stats['total_otps']}

📅 Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
    bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "waiting_broadcast"
    bot.edit_message_text("📢 Send the message to broadcast to all users:", 
                         call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_combo")
def admin_add_combo(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "add_combo_country"
    bot.edit_message_text("📥 Send country code (e.g., 20 for Egypt):", 
                         call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_del_combo")
def admin_del_combo(call):
    if not is_admin(call.from_user.id):
        return
    combos = get_all_combos()
    if not combos:
        bot.answer_callback_query(call.id, "❌ No combos to delete!", show_alert=True)
        return
    markup = types.InlineKeyboardMarkup()
    for code, idx in combos:
        name, flag, _ = COUNTRY_CODES.get(code, (code, "🌍", ""))
        markup.add(types.InlineKeyboardButton(f"🗑️ {flag} {name} (#{idx})", callback_data=f"del_combo_{code}_{idx}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
    bot.edit_message_text("Select combo to delete:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_combo_"))
def admin_del_combo_confirm(call):
    if not is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    code, idx = parts[2], int(parts[3])
    delete_combo(code, idx)
    bot.answer_callback_query(call.id, "✅ Deleted!", show_alert=True)
    admin_del_combo(call)

@bot.callback_query_handler(func=lambda call: call.data == "admin_ban")
def admin_ban(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "waiting_ban"
    bot.edit_message_text("🚫 Send user ID to ban:", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_unban")
def admin_unban(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "waiting_unban"
    bot.edit_message_text("✅ Send user ID to unban:", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_user_info")
def admin_user_info(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "waiting_user_info"
    bot.edit_message_text("👤 Send user ID to get info:", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_set_photo")
def admin_set_photo(call):
    if not is_admin(call.from_user.id):
        return
    user_states[call.from_user.id] = "waiting_photo"
    bot.edit_message_text("🖼️ Send the photo to set as welcome image:", 
                         call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_dashboard_url")
def admin_dashboard_url(call):
    if not is_admin(call.from_user.id):
        return
    dashboard_url = f"https://{os.environ.get('VERCEL_URL', 'localhost')}/login"
    text = f"""🔗 <b>Web Dashboard URL</b>

🌐 <b>Link:</b> <a href='{dashboard_url}'>{dashboard_url}</a>

📝 <b>Login Credentials:</b>
Username: <code>admin</code>
Password: <code>admin123</code>

⚠️ Change password after first login!"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                         parse_mode="HTML", reply_markup=markup)

# ======================
# 📨 معالجة رسائل الأدمن النصية
# ======================
user_states = {}

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_broadcast")
def handle_broadcast(msg):
    if not is_admin(msg.from_user.id):
        return
    users = get_all_users()
    count = 0
    for user in users:
        try:
            bot.copy_message(user[0], msg.chat.id, msg.message_id)
            count += 1
            time.sleep(0.05)
        except:
            pass
    bot.reply_to(msg, f"✅ Broadcast sent to {count} users!")
    del user_states[msg.from_user.id]

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "add_combo_country")
def handle_add_combo_country(msg):
    if not is_admin(msg.from_user.id):
        return
    code = msg.text.strip().replace("+", "")
    if code not in COUNTRY_CODES:
        bot.reply_to(msg, "❌ Invalid country code!")
        return
    user_states[msg.from_user.id] = {"step": "add_combo_numbers", "code": code}
    bot.reply_to(msg, f"Send numbers for {COUNTRY_CODES[code][0]} (one per line):")

@bot.message_handler(func=lambda msg: isinstance(user_states.get(msg.from_user.id), dict) and user_states[msg.from_user.id].get("step") == "add_combo_numbers")
def handle_add_combo_numbers(msg):
    if not is_admin(msg.from_user.id):
        return
    data = user_states[msg.from_user.id]
    code = data["code"]
    numbers = [clean_number(n) for n in msg.text.split("\n") if clean_number(n)]
    if not numbers:
        bot.reply_to(msg, "❌ No valid numbers found!")
        return
    save_combo(code, numbers)
    bot.reply_to(msg, f"✅ Added {len(numbers)} numbers for {COUNTRY_CODES[code][0]}!")
    del user_states[msg.from_user.id]

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_ban")
def handle_ban(msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text)
        ban_user(uid)
        bot.reply_to(msg, f"✅ User {uid} banned!")
    except:
        bot.reply_to(msg, "❌ Invalid ID!")
    del user_states[msg.from_user.id]

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_unban")
def handle_unban(msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text)
        unban_user(uid)
        bot.reply_to(msg, f"✅ User {uid} unbanned!")
    except:
        bot.reply_to(msg, "❌ Invalid ID!")
    del user_states[msg.from_user.id]

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_user_info")
def handle_user_info(msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text)
        user = get_user(uid)
        if user:
            info = f"""👤 <b>User Info</b>

ID: <code>{user[0]}</code>
Username: @{user[1] or 'None'}
Name: {user[2]} {user[3]}
Banned: {'Yes' if user[6] else 'No'}
Assigned Number: {user[5] or 'None'}
Joined: {user[9] if len(user) > 9 else 'Unknown'}"""
            bot.reply_to(msg, info, parse_mode="HTML")
        else:
            bot.reply_to(msg, "❌ User not found!")
    except:
        bot.reply_to(msg, "❌ Invalid ID!")
    del user_states[msg.from_user.id]

@bot.message_handler(content_types=['photo'], func=lambda msg: user_states.get(msg.from_user.id) == "waiting_photo")
def handle_welcome_photo(msg):
    if not is_admin(msg.from_user.id):
        return
    photo_id = msg.photo[-1].file_id
    set_setting("welcome_photo", photo_id)
    bot.reply_to(msg, "✅ Welcome photo saved!")
    del user_states[msg.from_user.id]

# ======================
# 🌐 Web Dashboard Routes (لوحة التحكم على الويب)
# ======================

@app.route('/login', methods=['GET', 'POST'])
def web_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, username, is_admin FROM web_users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['logged_in'] = True
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[2] == 1
            return redirect('/dashboard')
        else:
            return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/logout')
def web_logout():
    session.clear()
    return redirect('/login')

@app.route('/')
@app.route('/dashboard')
@login_required
def web_dashboard():
    stats = get_stats()
    # جلب آخر 20 OTP
    logs = get_otp_logs(20)
    # جلب الأرقام النشطة
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT number, assigned_to, timestamp FROM otp_logs GROUP BY number ORDER BY timestamp DESC LIMIT 20")
    active_numbers = c.fetchall()
    conn.close()
    
    return render_template('dashboard.html', 
                          stats=stats, 
                          logs=logs, 
                          active_numbers=active_numbers,
                          username=session.get('username'))

@app.route('/api/my_numbers', methods=['GET'])
def api_my_numbers():
    api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if not api_key:
        return jsonify({"success": False, "error": "API key required"}), 401
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE api_key=?", (api_key,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        return jsonify({"success": False, "error": "Invalid API key"}), 401
    
    user_id = user[0]
    user_data = get_user(user_id)
    number = user_data[5] if user_data else None
    
    if number:
        name, flag, code = get_country_info(number)
        return jsonify({
            "success": True,
            "count": 1,
            "numbers": [{
                "number": f"+{number}",
                "country": name,
                "flag": flag,
                "assigned_at": user_data[9] if len(user_data) > 9 else None
            }]
        })
    else:
        return jsonify({"success": True, "count": 0, "numbers": []})

@app.route('/api/my_otps', methods=['GET'])
def api_my_otps():
    api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if not api_key:
        return jsonify({"success": False, "error": "API key required"}), 401
    
    limit = request.args.get('limit', 50, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE api_key=?", (api_key,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        return jsonify({"success": False, "error": "Invalid API key"}), 401
    
    user_id = user[0]
    user_data = get_user(user_id)
    number = user_data[5] if user_data else None
    
    if not number:
        return jsonify({"success": True, "count": 0, "otps": []})
    
    logs = get_otp_logs(limit, number)
    otps = []
    for log in logs:
        otps.append({
            "number": f"+{log[1]}",
            "otp_code": log[2],
            "service": log[4] if len(log) > 4 else "Unknown",
            "message": log[3],
            "timestamp": log[5] if len(log) > 5 else None
        })
    
    return jsonify({
        "success": True,
        "count": len(otps),
        "otps": otps
    })

@app.route('/api/latest_otp', methods=['GET'])
def api_latest_otp():
    api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if not api_key:
        return jsonify({"success": False, "error": "API key required"}), 401
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE api_key=?", (api_key,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        return jsonify({"success": False, "error": "Invalid API key"}), 401
    
    user_id = user[0]
    user_data = get_user(user_id)
    number = user_data[5] if user_data else None
    
    if not number:
        return jsonify({"success": True, "has_otp": False})
    
    logs = get_otp_logs(1, number)
    if logs:
        log = logs[0]
        return jsonify({
            "success": True,
            "has_otp": True,
            "otp_code": log[2],
            "service": log[4] if len(log) > 4 else "Unknown",
            "message": log[3],
            "timestamp": log[5] if len(log) > 5 else None
        })
    else:
        return jsonify({"success": True, "has_otp": False})

@app.route('/webhook', methods=['POST'])
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
# 🔄 حلقة جلب الرسائل من iVasms (خلفية)
# ======================
sent_messages_cache = set()

def load_sent_cache():
    global sent_messages_cache
    if os.path.exists(SENT_MESSAGES_FILE):
        try:
            with open(SENT_MESSAGES_FILE, 'r') as f:
                sent_messages_cache = set(json.load(f))
        except:
            sent_messages_cache = set()

def save_sent_cache():
    with open(SENT_MESSAGES_FILE, 'w') as f:
        json.dump(list(sent_messages_cache), f)

def background_message_fetcher():
    load_sent_cache()
    print("[*] Starting background message fetcher...")
    
    while True:
        try:
            messages = fetch_ivasms_messages()
            new_count = 0
            
            for msg in messages:
                msg_hash = f"{msg['date']}_{msg['number']}_{msg['sms'][:50]}"
                
                if msg_hash not in sent_messages_cache:
                    phone = msg['number']
                    sms_text = msg['sms']
                    otp = extract_otp(sms_text)
                    service = detect_service(sms_text)
                    
                    # تسجيل في قاعدة البيانات
                    log_otp(phone, otp, sms_text, service)
                    
                    # إرسال للمستخدم المخصص
                    target_user = get_user_by_number(phone)
                    if target_user:
                        try:
                            name, flag, _ = get_country_info(phone)
                            service_emoji = "💬"
                            otp_msg = f"""✅ <b>New OTP Received!</b>

🔢 <b>Number:</b> <code>+{phone}</code>
🔧 <b>Service:</b> {service_emoji} {service}
📋 <b>Code:</b> <code>{otp}</code>
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

💡 Click the button below to copy the code"""
                            
                            markup = types.InlineKeyboardMarkup()
                            markup.add(types.InlineKeyboardButton("📋 Copy Code", callback_data=f"copy_{otp}"))
                            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{phone}"))
                            
                            bot.send_message(target_user, otp_msg, parse_mode="HTML", reply_markup=markup)
                        except Exception as e:
                            print(f"Failed to send to user {target_user}: {e}")
                    
                    # إرسال للمجموعات الأساسية
                    for chat_id in CHAT_IDS:
                        try:
                            name, flag, _ = get_country_info(phone)
                            otp_msg = f"""<b>{flag} {service}</b>
<b>📱 +{phone}</b>
<code>{otp}</code>
<i>{datetime.now().strftime('%H:%M:%S')}</i>"""
                            bot.send_message(chat_id, otp_msg, parse_mode="HTML")
                        except Exception as e:
                            print(f"Failed to send to group {chat_id}: {e}")
                    
                    sent_messages_cache.add(msg_hash)
                    new_count += 1
                    print(f"[+] New OTP: {phone} -> {otp} ({service})")
            
            if new_count > 0:
                save_sent_cache()
                
        except Exception as e:
            print(f"[!] Fetcher error: {e}")
            traceback.print_exc()
        
        time.sleep(REFRESH_INTERVAL)

# ======================
# 🚀 تشغيل التطبيق
# ======================
def set_webhook():
    vercel_url = os.environ.get('VERCEL_URL', 'localhost')
    webhook_url = f"https://{vercel_url}/webhook"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        print(f"Webhook set: {response.json()}")
    except Exception as e:
        print(f"Failed to set webhook: {e}")

# بدء الخلفية
threading.Thread(target=background_message_fetcher, daemon=True).start()

# تعيين webhook
set_webhook()    "last_check": None
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
