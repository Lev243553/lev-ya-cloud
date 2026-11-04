# bot.py — Нейро-Студия v12.1 (Убрана нижняя клавиатура, добавлена Админка)
import os, re, time, base64, uuid, sqlite3, logging, threading
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

FIRST_FREE_IMAGE = os.getenv("FIRST_FREE_IMAGE", "1") == "1"
REF_BONUS        = int(os.getenv("REF_BONUS", "3"))
RATE_LIMIT       = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))
DAILY_BONUS      = os.getenv("DAILY_BONUS_ENABLED", "1") == "1"

SUB_TARIFFS = {
    "start": {"title":"Старт",  "price": int(os.getenv("SUB_START_PRICE","290")), "limit": int(os.getenv("SUB_START_LIMIT","30")), "days":30},
    "pro":   {"title":"Про",    "price": int(os.getenv("SUB_PRO_PRICE","590")),   "limit": int(os.getenv("SUB_PRO_LIMIT","70")),   "days":30},
    "max":   {"title":"Максимум","price": int(os.getenv("SUB_MAX_PRICE","990")),  "limit": int(os.getenv("SUB_MAX_LIMIT","130")),  "days":30},
}

if not TOKEN or not POLZA_KEY:
    raise SystemExit("BOT_TOKEN / POLZA_API_KEY не заданы")

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
ESTIMATED    = {"image":15,"audio":20,"video":90,"tts":15,"stt":10,"edit":20,"animate":60,"upscale":30}
FILE_REQUIRED = {"edit","animate","upscale","stt"}
BAL_FIELD = {"image":"balance_img","audio":"balance_aud","video":"balance_vid","tts":"balance_tts",
             "stt":"balance_stt","edit":"balance_edit","animate":"balance_anim","upscale":"balance_up"}

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
        referrals INTEGER DEFAULT 0, referrer_id INTEGER DEFAULT 0,
        q_bought INTEGER DEFAULT 0, reward_claimed INTEGER DEFAULT 0,
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
        referrals,referrer_id,q_bought,reward_claimed,sub_plan,sub_until,sub_used,sub_auto,sub_id,
        last_bonus,sub_notified,onboarded,state,temp_model_id,temp_price
        FROM users WHERE user_id=?""", (uid,))
    r = cur.fetchone(); c.close()
    if not r: return None
    keys = ["username","is_banned","total_generated","free_image","free_audio","free_video",
            "balance_img","balance_aud","balance_vid","balance_tts","balance_stt","balance_edit",
            "balance_anim","balance_up","referrals","referrer_id","q_bought","reward_claimed",
            "sub_plan","sub_until","sub_used","sub_auto","sub_id",
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

# ==========================================================
# МЕНЮ И КЛАВИАТУРЫ
# ==========================================================
def main_menu(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🖼 Картинки", callback_data="cat_image"),
           types.InlineKeyboardButton("🎬 Видео", callback_data="cat_video"))
    kb.add(types.InlineKeyboardButton("🎵 Музыка", callback_data="cat_audio"),
           types.InlineKeyboardButton("🗣 Озвучка", callback_data="cat_tts"))
    kb.add(types.InlineKeyboardButton("📝 Расшифровка", callback_data="cat_stt"),
           types.InlineKeyboardButton("✏️ Редактор", callback_data="cat_edit"))
    kb.add(types.InlineKeyboardButton("🎞 Оживление", callback_data="cat_animate"),
           types.InlineKeyboardButton("🔍 Апскейл", callback_data="cat_upscale"))
    kb.add(types.InlineKeyboardButton("💰 Мой баланс", callback_data="menu_balance"),
           types.InlineKeyboardButton("🎫 Подписка", callback_data="menu_sub"))
    kb.add(types.InlineKeyboardButton("🛒 Купить", callback_data="menu_buy"),
           types.InlineKeyboardButton("📚 Мои работы", callback_data="menu_works"))
    kb.add(types.InlineKeyboardButton("🎁 Бонус дня", callback_data="menu_bonus"),
           types.InlineKeyboardButton("🏆 Задания", callback_data="menu_quest"))
    kb.add(types.InlineKeyboardButton("📞 Поддержка", url=SUPPORT_URL))
    
    # Админка
    if uid == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("🛡 Админ-панель", callback_data="admin_panel"))
        
    return kb

def back_menu():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_main"))

def cancel_kb():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Отмена", callback_data="menu_main"))

# ==========================================================
# СТАРТ И МЕНЮ
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
                u_new = get_user(uid)
                upd(uid, free_image=u_new["free_image"] + REF_BONUS)
    else:
        upd(uid, last_seen=time.time())

    u = get_user(uid)
    if u["is_banned"]: return bot.send_message(uid, "⛔ Вы забанены.")
    set_state(uid, "")

    # Убираем нижнюю клавиатуру, если она осталась от старых версий
    try: bot.send_message(uid, "Очистка...", reply_markup=types.ReplyKeyboardRemove())
    except: pass

    bonus = "\n\n🎁 <b>Тебе подарок:</b> 1 бесплатная картинка!" if (is_new and FIRST_FREE_IMAGE) else ""
    bot.send_message(uid, f"👋 Привет, @{uname}!\n\nЯ — <b>Нейро-Студия</b>.{bonus}\n\nВыбери, что хочешь сгенерировать:", reply_markup=main_menu(uid), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_main")
def cb_main(c):
    bot.answer_callback_query(c.id)
    bot.edit_message_text("Выбери, что хочешь сгенерировать:", c.message.chat.id, c.message.message_id, reply_markup=main_menu(c.from_user.id))

# ==========================================================
# АДМИНКА
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def cb_admin_panel(c):
    if c.from_user.id != ADMIN_ID: return bot.answer_callback_query(c.id, "Нет доступа", show_alert=True)
    bot.answer_callback_query(c.id)
    
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(total_generated),0) FROM users")
    users, gens = cur.fetchone()
    cc.close()
    
    txt = f"🛡 <b>Админ-панель</b>\n\n👥 Юзеров: {users}\n🎨 Генераций: {gens}\n\n<b>Команды:</b>\n<code>/add ID КОЛ-ВО</code> — выдать картинки\n<code>/admin</code> — справка"
    
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.message_handler(commands=['add'])
def admin_add(m):
    if m.from_user.id != ADMIN_ID: return
    try:
        _, uid, amount = m.text.split()
        uid, amount = int(uid), int(amount)
        u = get_user(uid)
        if not u: return bot.send_message(m.chat.id, "Нет юзера.")
        upd(uid, balance_img=u["balance_img"] + amount)
        bot.send_message(m.chat.id, f"✅ Выдано {amount} картинок юзеру {uid}")
        try: bot.send_message(uid, f"🎁 Тебе начислено {amount} генераций картинок!")
        except: pass
    except: bot.send_message(m.chat.id, "❌ Формат: /add 123456 10")

# ==========================================================
# ОСТАЛЬНЫЕ INLINE КНОПКИ
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data == "menu_balance")
def cb_balance(c):
    bot.answer_callback_query(c.id)
    u = get_user(c.from_user.id)
    sub_line = ""
    if sub_active(u):
        t = SUB_TARIFFS.get(u["sub_plan"], {})
        sub_line = f"\n\n🎫 Подписка «{t.get('title','?')}» до {datetime.fromtimestamp(u['sub_until']):%d.%m.%Y}\nИспользовано: {u['sub_used']}/{t.get('limit',0)}"
    else: sub_line = "\n\n🎫 Подписки нет."
    txt = f"💰 <b>Баланс</b>\n\n🖼 {u['balance_img']} | 🎵 {u['balance_aud']} | 🎬 {u['balance_vid']}\n🗣 {u['balance_tts']} | 📝 {u['balance_stt']} | ✏️ {u['balance_edit']}\n🎞 {u['balance_anim']} | 🔍 {u['balance_up']}\n\n🎁 Бесплатные: {u['free_image']} карт.\n👥 Рефералов: {u['referrals']}" + sub_line
    bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=back_menu(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_sub")
def cb_sub(c):
    bot.answer_callback_query(c.id)
    u = get_user(c.from_user.id)
    if sub_active(u):
        t = SUB_TARIFFS.get(u["sub_plan"], {})
        txt = f"🎫 <b>Подписка</b>\nТариф: <b>{t.get('title','?')}</b>\nДействует до: <b>{datetime.fromtimestamp(u['sub_until']):%d.%m.%Y}</b>\nИспользовано: <b>{u['sub_used']}/{t.get('limit',0)}</b>"
        kb = types.InlineKeyboardMarkup(row_width=1).add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    else:
        txt = "🎫 <b>Подписка</b>\n\nВыбери тариф:"
        kb = types.InlineKeyboardMarkup(row_width=1)
        for code, t in SUB_TARIFFS.items():
            kb.add(types.InlineKeyboardButton(f"{t['title']} — {t['limit']} ген. / {t['price']}₽", callback_data=f"sub_{code}"))
        kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_works")
def cb_works(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT id, m_type, model_id, prompt, file_id, ts FROM works WHERE user_id=? ORDER BY id DESC LIMIT 5", (uid,))
    rows = cur.fetchall(); cc.close()
    if not rows: return bot.edit_message_text("📚 Пока пусто.", c.message.chat.id, c.message.message_id, reply_markup=back_menu())
    bot.edit_message_text("📚 Отправляю...", c.message.chat.id, c.message.message_id, reply_markup=back_menu())
    for wid, m_type, model_id, prompt, file_id, ts in rows:
        caption = f"🕐 {datetime.fromtimestamp(ts):%d.%m %H:%M} | {MODELS.get(model_id, {}).get('name', model_id)}\n💬 {prompt[:100]}"
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
    txt = f"🏆 <b>Задания</b>\n\nПригласить друга: {u['referrals']}/1\n\n<i>Награда: 1 бесплатная картинка.</i>"
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔗 Пригласить", url=f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "menu_buy")
def cb_buy(c):
    bot.answer_callback_query(c.id)
    if setting("payments_on") != "1": return bot.answer_callback_query(c.id, "Оплата недоступна.", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACKAGES.items():
        kb.add(types.InlineKeyboardButton(f"{p['title']} — {p['price']}₽", callback_data=f"pay_{pid}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text("💳 <b>Пакеты</b>", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def cb_category(c):
    bot.answer_callback_query(c.id)
    if setting("generations_on") != "1": return bot.answer_callback_query(c.id, "Приостановлено.", show_alert=True)
    m_type = c.data.split("_")[1]
    models = active_by_type(m_type)
    if not models: return bot.answer_callback_query(c.id, "Отключено.", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for mid, price in models.items():
        suffix = "/сек" if m_type == "video" else ""
        kb.add(types.InlineKeyboardButton(f"{MODELS[mid]['name']} ({price}₽{suffix})", callback_data=f"mod_{mid}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_main"))
    bot.edit_message_text(f"Выбери модель:", c.message.chat.id, c.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_"))
def cb_model(c):
    bot.answer_callback_query(c.id)
    mid = c.data[4:]
    m = get_model(mid)
    if not m or not m["active"]: return bot.answer_callback_query(c.id, "Недоступно.", show_alert=True)
    m_type = MODELS[mid]["type"]

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
# ОПЛАТА
# ==========================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_") and c.data[4:] in SUB_TARIFFS)
def cb_sub_buy(c):
    bot.answer_callback_query(c.id)
    code = c.data[4:]; t = SUB_TARIFFS.get(code)
    if not (PLATEGA_ID and PLATEGA_SECRET): return bot.answer_callback_query(c.id, "Недоступно.", show_alert=True)
    bot.send_message(c.from_user.id, f"🎫 Для оплаты подписки напишите в поддержку: {SUPPORT_URL}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def cb_pay(c):
    bot.answer_callback_query(c.id)
    if not (PLATEGA_ID and PLATEGA_SECRET): return bot.answer_callback_query(c.id, "Недоступно.", show_alert=True)
    bot.send_message(c.from_user.id, f"💳 Для оплаты напишите в поддержку: {SUPPORT_URL}")

# ==========================================================
# ВВОД ПРОМПТА
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
        can_sub, _ = sub_can_use(u)
        if can_sub:
            upd(uid, sub_used=u["sub_used"] + 1); paid_by = "sub"
        elif m_type == "image" and u["free_image"] > 0:
            upd(uid, free_image=u["free_image"] - 1); paid_by = "free"
        elif deduct(uid, m_type):
            paid_by = "balance"
        else:
            return bot.send_message(uid, "❌ Нет средств. Купи в меню.")

    rate_add(uid)
    gen(uid, m, mid, m_type, u["temp_price"], is_admin, paid_by)

# ==========================================================
# ГЕНЕРАЦИЯ
# ==========================================================
def build_payload(mid, m_type, prompt, file_bytes=None, duration=None):
    inp = {"prompt": prompt}
    if duration: inp["duration"] = duration
    if file_bytes:
        b64 = base64.b64encode(file_bytes).decode()
        data_uri = f"data:image/jpeg;base64,{b64}"
        if m_type == "edit" or m_type == "animate": inp["images"] = [{"type": "base64", "data": data_uri}]
        elif m_type == "upscale": inp["videos" if "video" in mid else "images"] = [{"type": "base64", "data": data_uri}]
    return {"model": mid, "async": False, "input": inp}

def download_telegram_file(file_id):
    try: return bot.download_file(bot.get_file(file_id).file_path)
    except: return None

def transcribe(file_bytes, file_mime, mid):
    headers = {"Authorization": f"Bearer {POLZA_KEY}"}
    files = {"file": ("audio.ogg", file_bytes, file_mime or "audio/ogg")}
    data = {"model": mid}
    try:
        r = requests.post(f"{POLZA_BASE}/audio/transcriptions", headers=headers, files=files, data=data, timeout=120)
        return r.json().get("text") if r.status_code == 200 else None
    except: return None

def gen(uid, message, mid, m_type, price, is_admin, paid_by):
    prompt = message.text or message.caption or ""
    file_bytes = None
    if message.content_type in ("photo","video","voice","audio","document"):
        file_id = message.photo[-1].file_id if message.content_type == "photo" else getattr(message, message.content_type).file_id
        file_bytes = download_telegram_file(file_id)

    if m_type == "stt":
        status = bot.send_message(uid, "⏳ Расшифровка...")
        text = transcribe(file_bytes or b"", "audio/ogg", mid)
        try: bot.delete_message(uid, status.message_id)
        except: pass
        if not text:
            if paid_by == "balance": refund(uid, m_type)
            return bot.send_message(uid, "❌ Ошибка. Возвращено.")
        bot.send_message(uid, f"📝 <b>Расшифровка:</b>\n\n{text[:3500]}", parse_mode="HTML")
        return

    duration = None
    if m_type == "video" and price:
        duration = max(1, price // MODELS[mid]["price"]) if MODELS[mid]["price"] else 5

    payload = build_payload(mid, m_type, prompt, file_bytes, duration)
    headers = {"Authorization": f"Bearer {POLZA_KEY}", "Content-Type": "application/json"}
    status = bot.send_message(uid, f"⏳ Генерация ({m_type})...")

    try:
        r = requests.post(f"{POLZA_BASE}/media", headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            bot.edit_message_text(f"❌ Ошибка API. Возвращено.", uid, status.message_id)
            if paid_by == "balance": refund(uid, m_type)
            return

        data = r.json()
        if data.get("status") == "pending" and data.get("id"):
            deadline = time.time() + POLL_TIMEOUT.get(m_type, 120)
            while time.time() < deadline:
                time.sleep(2)
                chk = requests.get(f"{POLZA_BASE}/media/{data['id']}", headers=headers, timeout=15).json()
                if chk.get("status") == "completed": data = chk; break
                if chk.get("status") == "failed":
                    bot.edit_message_text("❌ Не удалось. Возвращено.", uid, status.message_id)
                    if paid_by == "balance": refund(uid, m_type)
                    return
            else:
                bot.edit_message_text("⏳ Таймаут. Возвращено.", uid, status.message_id)
                if paid_by == "balance": refund(uid, m_type)
                return

        url = data.get("data", [{}])[0].get("url") or data.get("url")
        if not url:
            bot.edit_message_text("❌ Нет ссылки. Возвращено.", uid, status.message_id)
            if paid_by == "balance": refund(uid, m_type)
            return

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
        upd(uid, total_generated=get_user(uid)["total_generated"] + 1)

    except Exception as e:
        try: bot.delete_message(uid, status.message_id)
        except: pass
        bot.send_message(uid, f"❌ Сбой. Возвращено.")
        if paid_by == "balance": refund(uid, m_type)

if __name__ == "__main__":
    log.info("🚀 Бот запущен (v12.1)")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
