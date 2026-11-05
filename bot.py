# bot.py — Нейро-Студия v22 (ФИНАЛ: Всё в одном файле)
import os, re, time, base64, uuid, sqlite3, logging, threading, json
from datetime import datetime
from dotenv import load_dotenv
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
import requests

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("neuro")

TOKEN         = os.getenv("BOT_TOKEN")
ADMIN_ID      = int(os.getenv("ADMIN_ID", "0"))
POLZA_KEY     = os.getenv("POLZA_API_KEY")
POLZA_BASE    = os.getenv("POLZA_API_URL", "https://polza.ai/api/v1")
DATA_DIR      = os.getenv("DATA_DIR", "./data")
SUPPORT_URL   = os.getenv("SUPPORT_URL", "https://t.me/crptworking")
PRIVACY_URL   = os.getenv("PRIVACY_URL", "")
TERMS_URL     = os.getenv("TERMS_URL", "")
PLATEGA_ID    = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET= os.getenv("PLATEGA_SECRET_KEY", "")
PLATEGA_URL   = os.getenv("PLATEGA_API_URL", "https://app.platega.io")
RETURN_URL    = os.getenv("RETURN_URL", "")
CHANNEL_ID    = os.getenv("CHANNEL_ID", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")

FIRST_FREE_IMAGE = os.getenv("FIRST_FREE_IMAGE", "1") == "1"
REF_BONUS        = int(os.getenv("REF_BONUS", "3"))
RATE_LIMIT       = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))
DAILY_BONUS      = os.getenv("DAILY_BONUS_ENABLED", "1") == "1"
FREE_TEXT_LIMIT  = 5

SUB_TARIFFS = {
    "start": {"title":"Старт",  "price": int(os.getenv("SUB_START_PRICE","290")), "limit": int(os.getenv("SUB_START_LIMIT","30")), "days":30},
    "pro":   {"title":"Про",    "price": int(os.getenv("SUB_PRO_PRICE","590")),   "limit": int(os.getenv("SUB_PRO_LIMIT","70")),   "days":30},
    "max":   {"title":"Максимум","price": int(os.getenv("SUB_MAX_PRICE","990")),  "limit": int(os.getenv("SUB_MAX_LIMIT","130")),  "days":30},
}

if not TOKEN or not POLZA_KEY: raise SystemExit("BOT_TOKEN / POLZA_API_KEY не заданы")
os.makedirs(DATA_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, "media_bot.db")
bot = telebot.TeleBot(TOKEN, threaded=True)

BOT_USERNAME = "plamenerualbot"
try: BOT_USERNAME = bot.get_me().username
except Exception as e: log.warning(f"get_me: {e}")

# ==========================================================
# МОДЕЛИ
# ==========================================================
MODELS = {
    # --- МЕДИА (Polza) ---
    "openai/gpt-image-1.5":               {"name":"GPT Image 1.5",       "type":"image",  "price":7,  "cost":3.0,  "active":1},
    "openai/gpt-5-image":                 {"name":"GPT-5 Image",         "type":"image",  "price":10, "cost":4.5,  "active":1},
    "google/gemini-2.5-flash-image":      {"name":"Gemini 2.5 Flash",    "type":"image",  "price":6,  "cost":2.9,  "active":1},
    "google/gemini-3.1-flash-lite-image": {"name":"Gemini 3.1 Lite",     "type":"image",  "price":6,  "cost":2.9,  "active":1},
    "google/gemini-nano-banana-2.1":      {"name":"Nano Banana 2.1",     "type":"image",  "price":7,  "cost":3.0,  "active":1},
    "black-forest-labs/flux.2-flex":      {"name":"Flux 2 Flex",         "type":"image",  "price":22, "cost":14.0, "active":1},
    "bytedance/seedream-4":               {"name":"Seedream 4",          "type":"image",  "price":7,  "cost":3.0,  "active":1},
    "bytedance/seedream-5-lite":          {"name":"Seedream 5 Lite",     "type":"image",  "price":8,  "cost":4.0,  "active":1},
    "qwen/image":                         {"name":"Qwen Image",          "type":"image",  "price":5,  "cost":2.25, "active":1},
    "qwen/image-2":                       {"name":"Qwen Image 2",        "type":"image",  "price":8,  "cost":4.0,  "active":1},
    "qwen/image-2.1":                     {"name":"Qwen Image 2.1",      "type":"image",  "price":7,  "cost":3.0,  "active":1},
    "tongyi-mai/z-image":                 {"name":"Z-Image",             "type":"image",  "price":5,  "cost":1.4,  "active":1},
    "yandex/yandex-art":                  {"name":"Yandex Art",          "type":"image",  "price":6,  "cost":2.91, "active":1},
    "grok-imagine-image-2-0/text-to-image":{"name":"Grok Image 2.0",     "type":"image",  "price":8,  "cost":3.0,  "active":1},
    "x-ai/grok-image":                    {"name":"Grok Image",          "type":"image",  "price":6,  "cost":2.5,  "active":1},
    "google/lyria-3-pro-preview":         {"name":"Lyria 3 Pro",         "type":"audio",  "price":20, "cost":10.0, "active":1},
    "suno/sounds":                        {"name":"Suno Sounds",         "type":"audio",  "price":8,  "cost":4.0,  "active":1},
    "google/lyria-3-clip-preview":        {"name":"Lyria 3 Clip",        "type":"audio",  "price":12, "cost":6.0,  "active":1},
    "grok-imagine-video-1-5":             {"name":"Grok Imagine Video",  "type":"video",  "price":5,  "cost":2.0,  "active":1},
    "bytedance/seedance-2-mini":          {"name":"Seedance 2 Mini",     "type":"video",  "price":7,  "cost":3.0,  "active":1},
    "google/gemini-3.8-flash-lite-tts":   {"name":"Gemini 3.8 TTS",      "type":"tts",    "price":15, "cost":7.0,  "active":1},
    "google/gemini-3.1-flash-tts-preview":{"name":"Gemini 3.1 TTS",      "type":"tts",    "price":30, "cost":14.0, "active":1},
    "openai/whisper-1":                   {"name":"Whisper 1",           "type":"stt",    "price":5,  "cost":0.43, "active":1},
    "openai/gpt-4o-transcribe":           {"name":"GPT-4o Transcribe",   "type":"stt",    "price":5,  "cost":0.70, "active":1},
    "bytedance/seedream-4.5":             {"name":"Seedream 4.5 Edit",   "type":"edit",   "price":8,  "cost":4.0,  "active":1},
    "bytedance/seedance-2":               {"name":"Seedance 2 (Оживл.)", "type":"animate","price":15, "cost":7.0,  "active":1},
    "kling/v2.6-motion-control":          {"name":"Kling Motion",        "type":"animate","price":20, "cost":10.0, "active":1},
    "topaz/video-upscale":                {"name":"Topaz Video Upscale", "type":"upscale","price":12, "cost":6.0,  "active":1},
    "topaz/image-upscale":                {"name":"Topaz Image Upscale", "type":"upscale","price":5,  "cost":2.0,  "active":1},
    
    # --- БЕСПЛАТНЫЙ ТЕКСТ (OpenRouter) ---
    "nvidia/nemotron-3-ultra-550b-a55b:free": {"name":"Nemotron 3 Ultra", "type":"text", "price":0, "cost":0.0, "active":1, "provider":"openrouter"},
    "google/gemma-4-31b-it:free":         {"name":"Gemma 4 31B",        "type":"text",   "price":0,  "cost":0.0,  "active":1, "provider":"openrouter"},
}

PACKAGES = {
    "img_10": {"title":"10 картинок",   "type":"image",  "count":10, "price":59},
    "img_25": {"title":"25 картинок",   "type":"image",  "count":25, "price":129},
    "img_50": {"title":"50 картинок",   "type":"image",  "count":50, "price":239},
    "img_100":{"title":"100 картинок",  "type":"image",  "count":100,"price":449},
    "aud_10": {"title":"10 музыки",     "type":"audio",  "count":10, "price":99},
    "aud_25": {"title":"25 музыки",     "type":"audio",  "count":25, "price":219},
    "vid_5":  {"title":"5 видео",       "type":"video",  "count":5,  "price":149},
    "vid_15": {"title":"15 видео",      "type":"video",  "count":15, "price":399},
    "tts_10": {"title":"10 озвучек",    "type":"tts",    "count":10, "price":139},
    "stt_10": {"title":"10 расшифровок","type":"stt",    "count":10, "price":59},
    "stt_25": {"title":"25 расшифровок","type":"stt",    "count":25, "price":129},
    "edit_10":{"title":"10 редакций",   "type":"edit",   "count":10, "price":99},
    "anim_5": {"title":"5 оживлений",   "type":"animate","count":5,  "price":99},
    "up_10":  {"title":"10 апскейлов",  "type":"upscale","count":10, "price":59},
}

POLL_TIMEOUT = {"image":120,"audio":120,"video":300,"tts":120,"stt":120,"edit":120,"animate":300,"upscale":180}
ESTIMATED    = {"image":15,"audio":20,"video":90,"tts":15,"stt":10,"edit":20,"animate":60,"upscale":30,"text":5}
FILE_REQUIRED = {"edit","animate","upscale","stt"}
BAL_FIELD = {"image":"balance_img","audio":"balance_aud","video":"balance_vid","tts":"balance_tts",
             "stt":"balance_stt","edit":"balance_edit","animate":"balance_anim","upscale":"balance_up"}
TYPE_NAMES = {"image":"🖼 Картинки", "audio":"🎵 Музыка", "video":"🎬 Видео", "tts":"🗣 Озвучка",
              "stt":"📝 Расшифровка", "edit":"✏️ Редактор", "animate":"🎞 Оживление", "upscale":"🔍 Апскейл",
              "text":"💬 Текст (AI)"}

BANNED = re.compile(r'\b(' + '|'.join(map(re.escape, [
    "порно","секс","эротика","хентай","изнасилование","педофил","лоли","цп","инцест",
    "насилие","убийство","оружие","наркотики","нацизм","гитлер","фашизм","терроризм"
])) + r')\b', re.IGNORECASE)

# ==========================================================
# БД
# ==========================================================
def conn():
    c = sqlite3.connect(DB, check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    c = conn(); cur = c.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT, is_banned INTEGER DEFAULT 0,
        total_generated INTEGER DEFAULT 0,
        free_image INTEGER DEFAULT 0, free_audio INTEGER DEFAULT 0, free_video INTEGER DEFAULT 0,
        balance_img INTEGER DEFAULT 0, balance_aud INTEGER DEFAULT 0, balance_vid INTEGER DEFAULT 0,
        balance_tts INTEGER DEFAULT 0, balance_stt INTEGER DEFAULT 0, balance_edit INTEGER DEFAULT 0,
        balance_anim INTEGER DEFAULT 0, balance_up INTEGER DEFAULT 0,
        text_free_used INTEGER DEFAULT 0,
        sub_plan TEXT DEFAULT '', sub_until REAL DEFAULT 0, sub_used INTEGER DEFAULT 0,
        sub_auto INTEGER DEFAULT 0, sub_id TEXT DEFAULT '',
        last_bonus REAL DEFAULT 0, sub_notified INTEGER DEFAULT 0,
        onboarded INTEGER DEFAULT 0,
        state TEXT DEFAULT '', temp_model_id TEXT DEFAULT '', temp_price INTEGER DEFAULT 0,
        created_at REAL DEFAULT 0, last_seen REAL DEFAULT 0)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS models(model_id TEXT PRIMARY KEY, active INTEGER, price INTEGER, cost REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, package_id TEXT, amount INTEGER, status TEXT, platega_id TEXT, ts REAL,
        kind TEXT DEFAULT 'package')''')
    cur.execute('''CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, action TEXT, details TEXT, ts REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promo(code TEXT PRIMARY KEY, type TEXT, value INTEGER, uses_left INTEGER)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS promo_used(code TEXT, user_id INTEGER, ts REAL, UNIQUE(code,user_id))''')
    cur.execute('''CREATE TABLE IF NOT EXISTS works(id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, m_type TEXT, model_id TEXT, prompt TEXT, file_id TEXT, ts REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS rate(user_id INTEGER, ts REAL)''')
    c.commit()
    
    try: cur.execute("ALTER TABLE users ADD COLUMN text_free_used INTEGER DEFAULT 0")
    except: pass
    
    for mid, m in MODELS.items():
        cur.execute("INSERT OR IGNORE INTO models VALUES(?,?,?,?)", (mid, m["active"], m["price"], m["cost"]))
    for k, v in {"payments_on":"1","generations_on":"1"}.items():
        cur.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    c.commit(); c.close()

init_db()

def get_user(uid):
    c = conn(); cur = c.cursor()
    cur.execute("""SELECT username,is_banned,total_generated,free_image,free_audio,free_video,
        balance_img,balance_aud,balance_vid,balance_tts,balance_stt,balance_edit,balance_anim,balance_up,
        text_free_used, referrals,referrer_id,q_bought,reward_claimed,sub_plan,sub_until,sub_used,
        sub_auto,sub_id, last_bonus,sub_notified,onboarded,state,temp_model_id,temp_price
        FROM users WHERE user_id=?""", (uid,))
    r = cur.fetchone(); c.close()
    if not r: return None
    keys = ["username","is_banned","total_generated","free_image","free_audio","free_video",
            "balance_img","balance_aud","balance_vid","balance_tts","balance_stt","balance_edit",
            "balance_anim","balance_up","text_free_used", "referrals","referrer_id","q_bought","reward_claimed",
            "sub_plan","sub_until","sub_used", "sub_auto","sub_id",
            "last_bonus","sub_notified","onboarded","state","temp_model_id","temp_price"]
    d = dict(zip(keys, r)); d["is_banned"] = bool(d["is_banned"]); return d

def add_user(uid, uname, ref=0):
    c = conn(); cur = c.cursor()
    cur.execute("INSERT OR IGNORE INTO users(user_id,username,referrer_id,created_at,last_seen) VALUES(?,?,?,?,?)",
                (uid, uname, ref, time.time(), time.time()))
    c.commit(); c.close()

def upd(uid, **kw):
    if not kw: return
    cols = ", ".join(f"{k}=?" for k in kw)
    c = conn(); cur = c.cursor()
    cur.execute(f"UPDATE users SET {cols} WHERE user_id=?", (*kw.values(), uid))
    c.commit(); c.close()

def set_state(uid, state, mid="", price=0):
    upd(uid, state=state, temp_model_id=mid, temp_price=price)

def deduct(uid, m_type):
    col = BAL_FIELD[m_type]
    c = conn(); cur = c.cursor()
    cur.execute(f"UPDATE users SET {col}={col}-1 WHERE user_id=? AND {col}>0", (uid,))
    ok = cur.rowcount > 0; c.commit(); c.close(); return ok

def refund(uid, m_type):
    col = BAL_FIELD[m_type]
    c = conn(); cur = c.cursor()
    cur.execute(f"UPDATE users SET {col}={col}+1 WHERE user_id=?", (uid,))
    c.commit(); c.close()

def log_ev(uid, action, details=""):
    c = conn(); cur = c.cursor()
    cur.execute("INSERT INTO logs(user_id,action,details,ts) VALUES(?,?,?,?)", (uid, action, details, time.time()))
    c.commit(); c.close()

def setting(k, d="1"):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (k,))
    r = cur.fetchone(); c.close(); return r[0] if r else d

def set_setting(k, v):
    c = conn(); cur = c.cursor()
    cur.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))
    c.commit(); c.close()

def get_model(mid):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT active,price,cost FROM models WHERE model_id=?", (mid,))
    r = cur.fetchone(); c.close()
    return {"active":r[0],"price":r[1],"cost":r[2]} if r else None

def active_by_type(m_type):
    c = conn(); cur = c.cursor()
    cur.execute("SELECT model_id,price FROM models WHERE active=1")
    rows = cur.fetchall(); c.close()
    return {m:p for m,p in rows if MODELS.get(m,{}).get("type") == m_type}

def add_work(uid, m_type, model_id, prompt, file_id):
    c = conn(); cur = c.cursor()
    cur.execute("INSERT INTO works(user_id,m_type,model_id,prompt,file_id,ts) VALUES(?,?,?,?,?,?)",
                (uid, m_type, model_id, prompt[:500], file_id, time.time()))
    cur.execute("""DELETE FROM works WHERE user_id=? AND id NOT IN
                   (SELECT id FROM works WHERE user_id=? ORDER BY id DESC LIMIT 100)""", (uid, uid))
    c.commit(); c.close()

def check_rate(uid):
    c = conn(); cur = c.cursor()
    cutoff = time.time() - 3600
    cur.execute("DELETE FROM rate WHERE ts < ?", (cutoff,))
    cur.execute("SELECT COUNT(*) FROM rate WHERE user_id=? AND ts>=?", (uid, cutoff))
    n = cur.fetchone()[0]
    c.commit(); c.close()
    return n < RATE_LIMIT

def rate_add(uid):
    c = conn(); cur = c.cursor()
    cur.execute("INSERT INTO rate(user_id,ts) VALUES(?,?)", (uid, time.time()))
    c.commit(); c.close()

def sub_active(u):
    return u["sub_plan"] and u["sub_until"] > time.time()

def sub_can_use(u):
    if not sub_active(u): return False, "нет подписки"
    t = SUB_TARIFFS.get(u["sub_plan"])
    if not t: return False, "неизвестный тариф"
    if u["sub_used"] >= t["limit"]: return False, f"лимит {t['limit']}/мес"
    return True, ""

def resolve_user(target_str):
    target_str = target_str.strip()
    if target_str.isdigit():
        uid = int(target_str)
        u = get_user(uid)
        return (uid, u["username"] if u else f"id{uid}")
    username = target_str.replace("@", "").lower()
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT user_id, username FROM users WHERE LOWER(username) = ?", (username,))
    row = cur.fetchone(); cc.close()
    if row: return row[0], row[1]
    try:
        chat = bot.get_chat(f"@{username}")
        uid = chat.id
        if not get_user(uid): add_user(uid, username)
        return uid, username
    except Exception:
        return None, None

# ==========================================================
# МЕНЮ
# ==========================================================
def main_menu(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🖼 Картинки", callback_data="cat_image"), types.InlineKeyboardButton("🎬 Видео", callback_data="cat_video"))
    kb.add(types.InlineKeyboardButton("🎵 Музыка", callback_data="cat_audio"), types.InlineKeyboardButton("🗣 Озвучка", callback_data="cat_tts"))
    kb.add(types.InlineKeyboardButton("📝 Расшифровка", callback_data="cat_stt"), types.InlineKeyboardButton("✏️ Редактор", callback_data="cat_edit"))
    kb.add(types.InlineKeyboardButton("🎞 Оживление", callback_data="cat_animate"), types.InlineKeyboardButton("🔍 Апскейл", callback_data="cat_upscale"))
    kb.add(types.InlineKeyboardButton("💬 Текст (AI)", callback_data="cat_text"))
    kb.add(types.InlineKeyboardButton("💰 Мой баланс", callback_data="menu_balance"), types.InlineKeyboardButton("🎫 Подписка", callback_data="menu_sub"))
    kb.add(types.InlineKeyboardButton("🛒 Купить", callback_data="menu_buy"), types.InlineKeyboardButton("📚 Мои работы", callback_data="menu_works"))
    kb.add(types.InlineKeyboardButton("🎁 Бонус дня", callback_data="menu_bonus"), types.InlineKeyboardButton("🏆 Задания", callback_data="menu_quest"))
    kb.add(types.InlineKeyboardButton("📞 Поддержка", url=SUPPORT_URL))
    if uid == ADMIN_ID: kb.add(types.InlineKeyboardButton("🛡 Админ-панель", callback_data="admin_root"))
    return kb

def back_menu():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_main"))

def cancel_kb():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Отмена", callback_data="menu_main"))

# ==========================================================
# СТАРТ
# ==========================================================
@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    uname = m.from_user.username or f"id{uid}"
    ref = 0
    p = (m.text or "").split()
    if len(p) > 1 and p[1].startswith("ref_"):
        try:
            ref = int(p[1].split("_")[1])
            if ref == uid: ref = 0
        except: ref = 0

    is_new = not get_user(uid)
    if is_new:
        add_user(uid, uname, ref)
        if FIRST_FREE_IMAGE: upd(uid, free_image=1)
        if ref:
            r = get_user(ref)
            if r:
                upd(ref, referrals=r["referrals"] + 1, free_image=r["free_image"] + REF_BONUS)
                try: bot.send_message(ref, f"🎉 По твоей ссылке пришёл друг! +{REF_BONUS} бесплатных картинок.")
                except: pass
                u_new = get_user(uid); upd(uid, free_image=u_new["free_image"] + REF_BONUS)
    else: upd(uid, last_seen=time.time())

    u = get_user(uid)
    if u["is_banned"]: return bot.send_message(uid, "⛔ Вы забанены.")
    set_state(uid, "")

    try: bot.send_message(uid, "Очистка...", reply_markup=types.ReplyKeyboardRemove())
    except: pass

    bonus = "\n\n🎁 <b>Тебе подарок:</b> 1 бесплатная картинка!" if (is_new and FIRST_FREE_IMAGE) else ""
    bot.send_message(uid, f"👋 Привет, @{uname}!\n\nЯ — <b>Нейро-Студия</b>.{bonus}\n\nВыбери, что хочешь сгенерировать:", reply_markup=main_menu(uid), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_main(c):
    bot.answer_callback_query(c.id)
    bot.edit_message_text("Выбери, что хочешь сгенерировать:", c.message.chat.id, c.message.message_id, reply_markup=main_menu(c.from_user.id))

# ==========================================================
# КАТЕГОРИИ И МОДЕЛИ
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def cb_category(c):
    bot.answer_callback_query(c.id)
    m_type = c.data.split("_")[1]
    
    if m_type == "text":
        u = get_user(c.from_user.id)
        if u["text_free_used"] >= FREE_TEXT_LIMIT:
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
            return bot.edit_message_text(f"❌ <b>Лимит бесплатных запросов исчерпан ({FREE_TEXT_LIMIT}/{FREE_TEXT_LIMIT})</b>.\n\nТекстовые запросы скоро будут доступны по подписке.", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    
    models = active_by_type(m_type)
    if not models: return bot.answer_callback_query(c.id, "Все модели выключены.", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for mid, price in models.items():
        suffix = "/сек" if m_type == "video" else ("₽" if price > 0 else "Free")
        btn_text = f"{MODELS[mid]['name']} ({price}{suffix})" if price > 0 else f"{MODELS[mid]['name']} (Free)"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"mod_{mid}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text(f"Выбери модель:", c.message.chat.id, c.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_"))
def cb_model(c):
    bot.answer_callback_query(c.id)
    mid = c.data[4:]
    m = get_model(mid)
    if not m or not m["active"]: return bot.answer_callback_query(c.id, "Недоступно.", show_alert=True)
    m_type = MODELS[mid]["type"]

    if m_type == "text":
        set_state(c.from_user.id, "waiting_for_prompt", mid, 0)
        return bot.edit_message_text(f"<b>{MODELS[mid]['name']}</b>.\nНапиши свой вопрос:", c.message.chat.id, c.message.message_id, reply_markup=cancel_kb(), parse_mode="HTML")

    if m["price"] >= 15 and m_type != "video":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton(f"✅ Да, {m['price']}₽", callback_data=f"conf_{mid}"), types.InlineKeyboardButton("❌ Нет", callback_data="menu_main"))
        return bot.edit_message_text(f"<b>{MODELS[mid]['name']}</b> — {m['price']}₽.\nТочно?", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

    if m_type == "video":
        kb = types.InlineKeyboardMarkup(row_width=3)
        for sec in (3, 5, 10): kb.add(types.InlineKeyboardButton(f"{sec}с ({sec*m['price']}₽)", callback_data=f"vdur_{sec}_{mid}"))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="cat_video"))
        return bot.edit_message_text(f"{MODELS[mid]['name']} — {m['price']}₽/сек.\nДлительность:", c.message.chat.id, c.message.message_id, reply_markup=kb)

    set_state(c.from_user.id, "waiting_for_prompt", mid, m["price"])
    hint = "Отправь файл (+ подпись = промпт)" if m_type in FILE_REQUIRED else "Напиши запрос"
    bot.edit_message_text(f"<b>{MODELS[mid]['name']}</b> ({m['price']}₽).\n{hint}:", c.message.chat.id, c.message.message_id, reply_markup=cancel_kb(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("conf_"))
def cb_confirm(c):
    bot.answer_callback_query(c.id)
    mid = c.data[5:]; m = get_model(mid)
    set_state(c.from_user.id, "waiting_for_prompt", mid, m["price"])
    hint = "Отправь файл" if MODELS[mid]["type"] in FILE_REQUIRED else "Напиши запрос"
    bot.edit_message_text(f"<b>{MODELS[mid]['name']}</b> ({m['price']}₽).\n{hint}:", c.message.chat.id, c.message.message_id, reply_markup=cancel_kb(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("vdur_"))
def cb_vdur(c):
    bot.answer_callback_query(c.id)
    _, sec, mid = c.data.split("_")
    sec = int(sec); m = get_model(mid)
    price = m["price"] * sec
    set_state(c.from_user.id, "waiting_for_prompt", mid, price)
    bot.edit_message_text(f"{MODELS[mid]['name']} — {sec} сек ({price}₽).\nЗапрос:", c.message.chat.id, c.message.message_id, reply_markup=cancel_kb())

# ==========================================================
# ВВОД И ГЕНЕРАЦИЯ
# ==========================================================
@bot.message_handler(content_types=["text","photo","video","voice","audio"])
def handle_input(m):
    uid = m.from_user.id
    u = get_user(uid)
    if not u or u["is_banned"]: return
    if u["state"] != "waiting_for_prompt":
        return bot.send_message(m.chat.id, "Выбери действие в меню: /start")

    mid = u["temp_model_id"]
    if mid not in MODELS: set_state(uid, ""); return
    m_type = MODELS[mid]["type"]

    if uid != ADMIN_ID and not check_rate(uid): return bot.send_message(m.chat.id, f"⏳ Лимит {RATE_LIMIT} ген/час.")
    check_text = (m.caption or "") if m.content_type != "text" else (m.text or "")
    if check_text and BANNED.search(check_text):
        set_state(uid, ""); return bot.send_message(m.chat.id, "❌ Запрещённые слова.")

    if m_type in FILE_REQUIRED and m.content_type == "text": return bot.send_message(m.chat.id, "⚠️ Нужен файл.")
    if m_type not in FILE_REQUIRED and m.content_type != "text": return bot.send_message(m.chat.id, "⚠️ Нужен текст.")

    set_state(uid, "")
    is_admin = (uid == ADMIN_ID); paid_by = None
    
    if not is_admin:
        if m_type == "text":
            if u["text_free_used"] < FREE_TEXT_LIMIT: upd(uid, text_free_used=u["text_free_used"]+1); paid_by = "free"
            else: return bot.send_message(uid, "❌ Лимит бесплатных текстовых запросов исчерпан.")
        else:
            can_sub, _ = sub_can_use(u)
            if can_sub: upd(uid, sub_used=u["sub_used"] + 1); paid_by = "sub"
            elif m_type == "image" and u["free_image"] > 0: upd(uid, free_image=u["free_image"] - 1); paid_by = "free"
            elif deduct(uid, m_type): paid_by = "balance"
            else: return bot.send_message(uid, "❌ Нет средств. Купи в меню.")

    rate_add(uid)
    gen(uid, m, mid, m_type, u["temp_price"], is_admin, paid_by)

def gen(uid, message, mid, m_type, price, is_admin, paid_by):
    prompt = message.text or message.caption or ""
    file_bytes = None
    if message.content_type in ("photo","video","voice","audio","document"):
        file_id = message.photo[-1].file_id if message.content_type == "photo" else getattr(message, message.content_type).file_id
        try: file_bytes = bot.download_file(bot.get_file(file_id).file_path)
        except: pass

    # ==================== ТЕКСТОВЫЕ ЗАПРОСЫ (OPENROUTER) ====================
    if m_type == "text":
        status = bot.send_message(uid, "💬 Думаю над ответом...")
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://t.me/plamenerualbot",
            "X-Title": "Neuro Studio"
        }
        payload = {"model": mid, "messages": [{"role": "user", "content": prompt}]}
        if "nemotron" in mid: payload["reasoning"] = {"enabled": True}

        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=90)
            if r.status_code != 200:
                try: err = r.json().get("error",{}).get("message", r.text[:200])
                except: err = r.text[:200]
                bot.edit_message_text(f"❌ Ошибка: {err}", uid, status.message_id)
                return
            
            data = r.json()
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            try: bot.delete_message(uid, status.message_id)
            except: pass
            if not answer: return bot.send_message(uid, "❌ Нейросеть не дала ответ.")
            if len(answer) > 4000:
                for i in range(0, len(answer), 4000): bot.send_message(uid, answer[i:i+4000])
            else: bot.send_message(uid, answer)
        except Exception as e:
            try: bot.delete_message(uid, status.message_id)
            except: pass
            bot.send_message(uid, "❌ Ошибка соединения.")
        return
    # ========================================================================

    # --- ОСТАЛЬНОЕ (МЕДИА) ---
    if m_type == "stt":
        status = bot.send_message(uid, "⏳ Расшифровка...")
        headers = {"Authorization": f"Bearer {POLZA_KEY}"}
        files = {"file": ("audio.ogg", file_bytes or b"", "audio/ogg")}
        try:
            r = requests.post(f"{POLZA_BASE}/audio/transcriptions", headers=headers, files=files, data={"model": mid}, timeout=120)
            text = r.json().get("text") if r.status_code == 200 else None
        except: text = None
        try: bot.delete_message(uid, status.message_id)
        except: pass
        if not text:
            if paid_by == "balance": refund(uid, m_type)
            return bot.send_message(uid, "❌ Ошибка. Возвращено.")
        return bot.send_message(uid, f"📝 <b>Расшифровка:</b>\n\n{text[:3500]}", parse_mode="HTML")

    duration = max(1, price // MODELS[mid]["price"]) if m_type == "video" and MODELS[mid]["price"] else None
    inp = {"prompt": prompt}
    if duration: inp["duration"] = duration
    if file_bytes:
        b64 = base64.b64encode(file_bytes).decode()
        if m_type in ("edit","animate"): inp["images"] = [{"type": "base64", "data": f"data:image/jpeg;base64,{b64}"}]
        elif m_type == "upscale": inp["videos" if "video" in mid else "images"] = [{"type": "base64", "data": f"data:image/jpeg;base64,{b64}"}]

    payload = {"model": mid, "async": False, "input": inp}
    headers = {"Authorization": f"Bearer {POLZA_KEY}", "Content-Type": "application/json"}
    status = bot.send_message(uid, f"⏳ Генерация...")

    try:
        r = requests.post(f"{POLZA_BASE}/media", headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            bot.edit_message_text("❌ Ошибка API. Возвращено.", uid, status.message_id)
            if paid_by == "balance": refund(uid, m_type)
            return
        data = r.json()
        if data.get("status") == "pending":
            deadline = time.time() + POLL_TIMEOUT.get(m_type, 120)
            while time.time() < deadline:
                time.sleep(2)
                chk = requests.get(f"{POLZA_BASE}/media/{data['id']}", headers=headers).json()
                if chk.get("status") == "completed": data = chk; break
                if chk.get("status") == "failed": raise Exception("fail")
            else: raise Exception("timeout")

        url = data.get("data", [{}])[0].get("url") or data.get("url")
        if not url: raise Exception("no url")

        fresp = requests.get(url, timeout=180)
        ext = {"image":".jpg","audio":".mp3","tts":".ogg","video":".mp4","edit":".jpg","animate":".mp4","upscale":".bin"}.get(m_type,".bin")
        tmp = f"temp_{uid}{ext}"
        with open(tmp,"wb") as f: f.write(fresp.content)
        try: bot.delete_message(uid, status.message_id)
        except: pass

        with open(tmp,"rb") as f:
            if m_type == "image": bot.send_photo(uid, f, caption="🎨 Готово")
            elif m_type == "tts": bot.send_voice(uid, f, caption="🗣 Готово")
            elif m_type == "audio": bot.send_audio(uid, f, caption="🎵 Готово")
            elif m_type in ("video","animate"): bot.send_video(uid, f, caption="🎬 Готово")
            else: bot.send_document(uid, f, caption="📁 Готово")
        os.remove(tmp)

    except Exception:
        try: bot.delete_message(uid, status.message_id)
        except: pass
        bot.send_message(uid, "❌ Сбой генерации. Возвращено.")
        if paid_by == "balance": refund(uid, m_type)

# ==========================================================
# ОСТАЛЬНЫЕ КНОПКИ
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_balance")
def cb_balance(c):
    bot.answer_callback_query(c.id)
    u = get_user(c.from_user.id)
    txt = f"💰 <b>Баланс</b>\n\n🖼 {u['balance_img']} | 🎵 {u['balance_aud']} | 🎬 {u['balance_vid']}\n🗣 {u['balance_tts']} | 📝 {u['balance_stt']} | ✏️ {u['balance_edit']}\n🎞 {u['balance_anim']} | 🔍 {u['balance_up']}\n\n🎁 Бесплатные: {u['free_image']} карт.\n💬 Текстовые запросы: {u['text_free_used']}/{FREE_TEXT_LIMIT}"
    bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=back_menu(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_works")
def cb_works(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT m_type, model_id, prompt, file_id, ts FROM works WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
    rows = cur.fetchall(); cc.close()
    if not rows: return bot.edit_message_text("📚 Пока пусто.", c.message.chat.id, c.message.message_id, reply_markup=back_menu())
    bot.edit_message_text("📚 Отправляю...", c.message.chat.id, c.message.message_id, reply_markup=back_menu())
    for m_type, model_id, prompt, file_id, ts in rows:
        caption = f"🕐 {datetime.fromtimestamp(ts):%d.%m %H:%M} | {MODELS.get(model_id, {}).get('name', model_id)}"
        try:
            if m_type == "image": bot.send_photo(uid, file_id, caption=caption)
            elif m_type == "tts": bot.send_voice(uid, file_id, caption=caption)
            elif m_type == "audio": bot.send_audio(uid, file_id, caption=caption)
            elif m_type in ("video","animate"): bot.send_video(uid, file_id, caption=caption)
            else: bot.send_document(uid, file_id, caption=caption)
        except: pass

@bot.callback_query_handler(func=lambda c: c.data == "menu_bonus")
def cb_bonus(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id; u = get_user(uid)
    if not DAILY_BONUS: return bot.answer_callback_query(c.id, "Отключено.", show_alert=True)
    if sub_active(u): return bot.answer_callback_query(c.id, "У тебя есть подписка!", show_alert=True)
    if time.time() - (u["last_bonus"] or 0) < 86400:
        left = int((86400 - (time.time() - u["last_bonus"])) / 3600) + 1
        return bot.answer_callback_query(c.id, f"Жди еще ~{left} ч.", show_alert=True)
    upd(uid, free_image=u["free_image"] + 1, last_bonus=time.time())
    bot.answer_callback_query(c.id, "🎁 +1 бесплатная картинка!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "menu_quest")
def cb_quest(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id; u = get_user(uid)
    txt = f"🏆 <b>Задания</b>\n\nПригласить друга: {u['referrals']}/1"
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔗 Пригласить", url=f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_buy")
def cb_buy(c):
    bot.answer_callback_query(c.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACKAGES.items():
        kb.add(types.InlineKeyboardButton(f"{p['title']} — {p['price']}₽", callback_data=f"pay_{pid}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text("💳 <b>Пакеты</b>", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_sub")
def cb_sub(c):
    bot.answer_callback_query(c.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for code, t in SUB_TARIFFS.items():
        kb.add(types.InlineKeyboardButton(f"{t['title']} — {t['limit']} ген. / {t['price']}₽", callback_data=f"sub_{code}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text("🎫 <b>Подписки на генерации:</b>", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_") or c.data.startswith("sub_"))
def cb_payment(c):
    bot.answer_callback_query(c.id, "⚠️ Оплата временно недоступна (на проверке Platega).", show_alert=True)

# ==========================================================
# АДМИНКА
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_") and c.from_user.id == ADMIN_ID)
def admin_router(c):
    bot.answer_callback_query(c.id)
    act = c.data.split("_")[1]
    
    if act == "root":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("📊 Дашборд", callback_data="admin_dash"), types.InlineKeyboardButton("👥 Юзеры", callback_data="admin_users"))
        kb.add(types.InlineKeyboardButton("💳 Платежи", callback_data="admin_pays"), types.InlineKeyboardButton("⚙️ Модели", callback_data="admin_models"))
        kb.add(types.InlineKeyboardButton("📜 Логи", callback_data="admin_logs"), types.InlineKeyboardButton("⬅️ В меню", callback_data="menu_main"))
        bot.edit_message_text("🛡 <b>Админ-панель</b>", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
        
    elif act == "dash":
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(total_generated),0) FROM users")
        users, gens = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM users WHERE sub_until > ?", (time.time(),))
        subs = cur.fetchone()[0]
        cc.close()
        txt = f"📊 <b>Дашборд</b>\n\n👥 Юзеров: {users}\n🎨 Генераций: {gens}\n🎫 Подписок: {subs}\n\nОплата: {'✅' if setting('payments_on')=='1' else '🛑'}\nГенерации: {'✅' if setting('generations_on')=='1' else '🛑'}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_root"))
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif act == "users":
        kb = types.InlineKeyboardMarkup(row_width=1)
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT user_id, username FROM users ORDER BY last_seen DESC LIMIT 15")
        rows = cur.fetchall(); cc.close()
        for uid, uname in rows:
            kb.add(types.InlineKeyboardButton(f"@{uname} (ID: {uid})", callback_data=f"a_view_{uid}"))
        kb.add(types.InlineKeyboardButton("🔍 Найти по @username", callback_data="admin_find_username"))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_root"))
        bot.edit_message_text("👥 <b>Последние юзеры:</b>", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif act == "find_username":
        msg = bot.send_message(c.message.chat.id, "Введи <code>@username</code> или <code>ID</code>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_find_and_show)

    elif act == "pays":
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT user_id,package_id,amount,status,ts FROM payments ORDER BY id DESC LIMIT 15")
        rows = cur.fetchall(); cc.close()
        txt = "💳 <b>Платежи</b>\n\n" + ("\n".join([f"• {u} | {p} | {a}₽ | {s} | {datetime.fromtimestamp(t):%d.%m %H:%M}" for u,p,a,s,t in rows]) if rows else "Пусто")
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_root"))
        bot.edit_message_text(txt[:4000], c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

    elif act == "models":
        kb = types.InlineKeyboardMarkup(row_width=1)
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT model_id, active FROM models")
        for mid, a in cur.fetchall():
            kb.add(types.InlineKeyboardButton(f"{'🟢' if a else '🔴'} {MODELS.get(mid,{}).get('name',mid)}", callback_data=f"m_toggle_{mid}"))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_root"))
        bot.edit_message_text("⚙️ Управление моделями:", c.message.chat.id, c.message.message_id, reply_markup=kb)

    elif act == "logs":
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT user_id,action,details,ts FROM logs ORDER BY id DESC LIMIT 15")
        rows = cur.fetchall(); cc.close()
        txt = "📜 <b>Логи</b>\n\n" + ("\n".join([f"• {datetime.fromtimestamp(t):%d.%m %H:%M} | {u} | {a} | {d}" for u,a,d,t in rows]) if rows else "Пусто")
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_root"))
        bot.edit_message_text(txt[:4000], c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

def admin_find_and_show(m):
    uid, uname = resolve_user(m.text)
    if not uid: return bot.send_message(m.chat.id, "❌ Не найден.")
    show_user_card(m.chat.id, uid, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("a_view_") and c.from_user.id == ADMIN_ID)
def cb_view_user(c):
    bot.answer_callback_query(c.id)
    uid = int(c.data.split("_")[2])
    show_user_card(c.message.chat.id, uid, c.message.message_id)

def show_user_card(chat_id, uid, msg_id=None):
    u = get_user(uid)
    if not u: return bot.send_message(chat_id, "❌ Нет юзера.")
    txt = f"👤 <b>@{u['username']}</b> (ID: <code>{uid}</code>)\nГенераций: {u['total_generated']}\n\n🖼{u['balance_img']} 🎵{u['balance_aud']} 🎬{u['balance_vid']}\n🗣{u['balance_tts']} 📝{u['balance_stt']} ✏️{u['balance_edit']}\n🎞{u['balance_anim']} 🔍{u['balance_up']}\n\nТекст: {u['text_free_used']}/{FREE_TEXT_LIMIT}\n{'🚫 ЗАБАНЕН' if u['is_banned'] else '✅ Активен'}"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("⭐ Выдать баланс", callback_data=f"a_give_{uid}"))
    ban_text = "✅ Разбанить" if u["is_banned"] else "🚫 Забанить"
    kb.add(types.InlineKeyboardButton(ban_text, callback_data=f"a_ban_{uid}"))
    kb.add(types.InlineKeyboardButton("⬅️ К списку", callback_data="admin_users"))
    
    if msg_id: bot.edit_message_text(txt, chat_id, msg_id, reply_markup=kb, parse_mode="HTML")
    else: bot.send_message(chat_id, txt, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("a_ban_") and c.from_user.id == ADMIN_ID)
def cb_ban_user(c):
    bot.answer_callback_query(c.id)
    uid = int(c.data.split("_")[2])
    u = get_user(uid)
    upd(uid, is_banned=not u["is_banned"])
    show_user_card(c.message.chat.id, uid, c.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("a_give_") and c.from_user.id == ADMIN_ID)
def cb_give_start(c):
    bot.answer_callback_query(c.id)
    uid = int(c.data.split("_")[2])
    kb = types.InlineKeyboardMarkup(row_width=2)
    for m_type, name in TYPE_NAMES.items():
        if m_type != "text": # Текст теперь бесплатный
            kb.add(types.InlineKeyboardButton(name, callback_data=f"a_gtype_{m_type}_{uid}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"a_view_{uid}"))
    bot.edit_message_text("Что выдать?", c.message.chat.id, c.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("a_gtype_") and c.from_user.id == ADMIN_ID)
def cb_give_type(c):
    bot.answer_callback_query(c.id)
    _, _, m_type, uid = c.data.split("_")
    uid = int(uid)
    msg = bot.send_message(c.message.chat.id, f"Введи количество для <b>{TYPE_NAMES[m_type]}</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, admin_do_gift_btn, uid, m_type)

def admin_do_gift_btn(m, uid, m_type):
    try:
        n = int(m.text.strip())
        u = get_user(uid)
        if not u: return bot.send_message(m.chat.id, "❌ Нет юзера.")
        if m_type not in BAL_FIELD: return
        
        upd(uid, **{BAL_FIELD[m_type]: u[BAL_FIELD[m_type]] + n})
        bot.send_message(m.chat.id, f"✅ Выдано {n} {m_type} юзеру @{u['username']}")
        show_user_card(m.chat.id, uid)
        try: bot.send_message(uid, f"🎁 Тебе начислено {n} ({m_type})")
        except: pass
    except:
        bot.send_message(m.chat.id, "❌ Введи число.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("m_toggle_") and c.from_user.id == ADMIN_ID)
def cb_m_toggle(c):
    bot.answer_callback_query(c.id)
    mid = c.data[len("m_toggle_"):]
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT active FROM models WHERE model_id=?", (mid,))
    r = cur.fetchone()
    if r:
        new = 0 if r[0] else 1
        cur.execute("UPDATE models SET active=? WHERE model_id=?", (new, mid))
        cc.commit()
    cc.close()
    bot.answer_callback_query(c.id, "Изменено.", show_alert=True)
    admin_router(types.CallbackQuery(id="", from_user=c.from_user, data="admin_models", message=c.message))

if __name__ == "__main__":
    log.info("🚀 Бот запущен (v22 ФИНАЛ)")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
