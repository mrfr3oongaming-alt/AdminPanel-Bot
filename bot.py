import time
import requests
import json
import re
import os
import sqlite3
import telebot
from telebot import types
import threading
import random
from datetime import datetime
from bs4 import BeautifulSoup

# ====================== الإعدادات ======================
BOT_TOKEN = "8837371310:AAEV6xQO0Bhsl0xMjDqTrq-1YWt1yTvnmVo"
ADMIN_IDS = [7244261447]
CHAT_IDS = ["-1003957679217"]

IVASMS_USERNAME = "3adhammohamed@gmail.com"
IVASMS_PASSWORD = "ytytyt3212"
IVASMS_LOGIN_URL = "https://ivas.tempnum.qzz.io/login"
IVASMS_BASE_URL = "https://ivas.tempnum.qzz.io"
IVASMS_SMS_API = "https://ivas.tempnum.qzz.io/portal/sms/received/getsms"

BOT_GROUP_LINK = "https://t.me/NumPlus0TP"
BOT_OWNER_USERNAME = "@jq_b4"
REFRESH_INTERVAL = 5
DB_PATH = "bot.db"

# ====================== قاموس الدول ======================
COUNTRY_CODES = {
    "20": ("Egypt", "🇪🇬"),
    "966": ("Saudi Arabia", "🇸🇦"),
    "971": ("UAE", "🇦🇪"),
    "1": ("USA/Canada", "🇺🇸"),
    "44": ("United Kingdom", "🇬🇧"),
    "49": ("Germany", "🇩🇪"),
    "33": ("France", "🇫🇷"),
    "90": ("Turkey", "🇹🇷"),
    "212": ("Morocco", "🇲🇦"),
    "213": ("Algeria", "🇩🇿"),
    "216": ("Tunisia", "🇹🇳"),
    "218": ("Libya", "🇱🇾"),
    "249": ("Sudan", "🇸🇩"),
    "965": ("Kuwait", "🇰🇼"),
    "974": ("Qatar", "🇶🇦"),
    "962": ("Jordan", "🇯🇴"),
    "964": ("Iraq", "🇮🇶"),
    "91": ("India", "🇮🇳"),
}

# ====================== قاعدة البيانات ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        is_banned INTEGER DEFAULT 0,
        assigned_number TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS combos (
        country_code TEXT PRIMARY KEY,
        numbers TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sent_messages (
        msg_hash TEXT PRIMARY KEY
    )''')
    c.execute("INSERT OR IGNORE INTO combos (country_code, numbers) VALUES (?, ?)",
              ("20", json.dumps(["20123456789", "20115555333"])))
    conn.commit()
    conn.close()

init_db()

# ====================== دوال مساعدة ======================
def clean_number(num):
    return re.sub(r'\D', '', str(num))

def extract_otp(msg):
    match = re.search(r'\b(\d{4,8})\b', msg)
    return match.group(1) if match else "N/A"

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def save_user(user_id, username=""):
    if not get_user(user_id):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO users (user_id, username) VALUES (?,?)", (user_id, username))
        conn.commit()
        conn.close()

def ban_user(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

def unban_user(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

def is_banned(uid):
    u = get_user(uid)
    return u and u[2] == 1

def get_combo(country_code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT numbers FROM combos WHERE country_code=?", (country_code,))
    row = c.fetchone()
    conn.close()
    return json.loads(row[0]) if row else []

def save_combo(country_code, numbers):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO combos (country_code, numbers) VALUES (?,?)", (country_code, json.dumps(numbers)))
    conn.commit()
    conn.close()

def assign_number(uid, number):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET assigned_number=? WHERE user_id=?", (number, uid))
    conn.commit()
    conn.close()

def get_available_numbers(country_code):
    all_nums = get_combo(country_code)
    if not all_nums:
        return []
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT assigned_number FROM users WHERE assigned_number IS NOT NULL")
    used = set(row[0] for row in c.fetchall())
    conn.close()
    return [n for n in all_nums if n not in used]

# ====================== iVasms Client ======================
class IvasmsClient:
    def __init__(self):
        self.session = requests.Session()
        self.logged_in = False

    def login(self):
        try:
            print("[iVasms] جاري تسجيل الدخول...")
            r = self.session.get(IVASMS_LOGIN_URL, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            token = soup.find('input', {'name': '_token'})
            csrf = token.get('value') if token else None
            payload = {'email': IVASMS_USERNAME, 'password': IVASMS_PASSWORD}
            if csrf:
                payload['_token'] = csrf
            resp = self.session.post(IVASMS_LOGIN_URL, data=payload, timeout=15)
            self.logged_in = 'login' not in resp.url.lower()
            print(f"[iVasms] {'✅ نجح' if self.logged_in else '❌ فشل'}")
            return self.logged_in
        except Exception as e:
            print(f"[iVasms] خطأ: {e}")
            return False

    def fetch_messages(self):
        if not self.logged_in and not self.login():
            return []
        try:
            today = datetime.now().strftime('%m/%d/%Y')
            data = {'from': today, 'to': today}
            headers = {'X-Requested-With': 'XMLHttpRequest'}
            resp = self.session.post(IVASMS_SMS_API, headers=headers, data=data, timeout=10)
            if resp.status_code != 200:
                self.logged_in = False
                return []
            soup = BeautifulSoup(resp.text, 'html.parser')
            rows = soup.select('table tbody tr')
            messages = []
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    phone = clean_number(cols[1].text.strip())
                    sms = cols[2].text.strip()
                    if phone and sms:
                        messages.append({'number': phone, 'message': sms})
            return messages
        except Exception as e:
            print(f"[iVasms] جلب: {e}")
            return []

ivasms = IvasmsClient()
bot = telebot.TeleBot(BOT_TOKEN)

# ====================== أوامر البوت ======================
@bot.message_handler(commands=['start'])
def start_cmd(msg):
    uid = msg.from_user.id
    if is_banned(uid):
        bot.reply_to(msg, "🚫 محظور")
        return
    save_user(uid, msg.from_user.username or "")
    markup = types.InlineKeyboardMarkup(row_width=2)
    for code, (name, flag) in COUNTRY_CODES.items():
        if get_combo(code):
            markup.add(types.InlineKeyboardButton(f"{flag} {name}", callback_data=f"country_{code}"))
    if uid in ADMIN_IDS:
        markup.add(types.InlineKeyboardButton("🔐 Admin", callback_data="admin_panel"))
    bot.send_message(uid, "🌟 اهلا بك في بوت NumPluse!\nاختر الدولة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def select_country(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "محظور", show_alert=True)
        return
    code = call.data.split("_")[1]
    available = get_available_numbers(code)
    if not available:
        bot.answer_callback_query(call.id, "❌ لا توجد أرقام", show_alert=True)
        return
    num = random.choice(available)
    assign_number(uid, num)
    name, flag = COUNTRY_CODES.get(code, ("", ""))
    msg = f"✅ رقمك: <code>{num}</code>\n🌍 {flag} {name}\n⏳ انتظر الرسائل..."
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 احصائيات", callback_data="stats"))
    markup.add(types.InlineKeyboardButton("📢 اذاعة", callback_data="broadcast"))
    markup.add(types.InlineKeyboardButton("🚫 حظر", callback_data="ban"))
    markup.add(types.InlineKeyboardButton("✅ الغاء حظر", callback_data="unban"))
    bot.edit_message_text("🔐 لوحة الادمن", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "stats")
def stats(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    conn.close()
    bot.answer_callback_query(call.id, f"👥 المستخدمين: {users}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "broadcast")
def broadcast_step(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states[call.from_user.id] = "waiting_broadcast"
    bot.edit_message_text("📢 ارسل الرسالة:", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "ban")
def ban_step(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states[call.from_user.id] = "waiting_ban"
    bot.edit_message_text("🚫 ارسل ID المستخدم:", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "unban")
def unban_step(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    user_states[call.from_user.id] = "waiting_unban"
    bot.edit_message_text("✅ ارسل ID المستخدم:", call.message.chat.id, call.message.message_id)

# ====================== معالجة الرسائل ======================
user_states = {}

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_broadcast")
def do_broadcast(msg):
    if msg.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    count = 0
    for uid in users:
        try:
            bot.copy_message(uid, msg.chat.id, msg.message_id)
            count += 1
            time.sleep(0.05)
        except:
            pass
    bot.reply_to(msg, f"✅ تم الارسال لـ {count} مستخدم")
    del user_states[msg.from_user.id]

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_ban")
def do_ban(msg):
    try:
        uid = int(msg.text.strip())
        ban_user(uid)
        bot.reply_to(msg, f"✅ تم حظر {uid}")
    except:
        bot.reply_to(msg, "❌ ID غلط")
    del user_states[msg.from_user.id]

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "waiting_unban")
def do_unban(msg):
    try:
        uid = int(msg.text.strip())
        unban_user(uid)
        bot.reply_to(msg, f"✅ تم فك حظر {uid}")
    except:
        bot.reply_to(msg, "❌ ID غلط")
    del user_states[msg.from_user.id]

# ====================== إرسال الرسائل ======================
def send_otp(phone, sms):
    otp = extract_otp(sms)
    formatted = f"📩 رسالة جديدة\n📞 <code>{phone}</code>\n🔑 <code>{otp}</code>"
    keyboard = json.dumps({"inline_keyboard": [[{"text": f"📋 COPY {otp}", "callback_data": f"copy_{otp}"}]]})
    for cid in CHAT_IDS:
        try:
            bot.send_message(cid, formatted, parse_mode="HTML", reply_markup=keyboard)
        except:
            pass
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, formatted, parse_mode="HTML")
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_"))
def copy_code(call):
    otp = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, f"✅ تم نسخ: {otp}", show_alert=True)

# ====================== جلب الرسائل ======================
sent_hashes = set()

def poller():
    while True:
        try:
            for msg in ivasms.fetch_messages():
                h = f"{msg['number']}_{msg['message'][:50]}"
                if h not in sent_hashes:
                    print(f"[+] {msg['number']} -> {extract_otp(msg['message'])}")
                    send_otp(msg['number'], msg['message'])
                    sent_hashes.add(h)
                    if len(sent_hashes) > 500:
                        sent_hashes.clear()
        except:
            pass
        time.sleep(REFRESH_INTERVAL)

# ====================== التشغيل ======================
if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════╗
║                                       ║
║     🚀 AdminPanel-Bot STARTED         ║
║                                       ║
║     👑 DEVELOPER : @jq_b4             ║
║     📢 CHANNEL   : @NumPlus0TP        ║
║                                       ║
╚═══════════════════════════════════════╝
    """)
    threading.Thread(target=poller, daemon=True).start()
    bot.infinity_polling()