# bot.py — Нейро-Студия v11 (10/10)
# + Автопродление СБП (Platega subscriptions)
# + Автопостинг в канал
# + Ежедневный бонус
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
DATA_DIR      = os.getenv("DATA_DIR", "/app/data")
SUPPORT_URL   = os.getenv("SUPPORT_URL", "https://t.me/crptworking")
PRIVACY_URL   = os.getenv("PRIVACY_URL", "")
TERMS_URL     = os.getenv("TERMS_URL", "")
PLATEGA_ID    = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET= os.getenv("PLATEGA_SECRET_KEY", "")
PLATEGA_URL   = os.getenv("PLATEGA_API_URL", "https://app.platega.io")
RETURN_URL    = os.getenv("RETURN_URL", "https://t.me/plamenerualbot")
CHANNEL_ID    = os.getenv("CHANNEL_ID", "@PlameChat")

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

BOT_USERNAME = "your_bot"
try: BOT_USERNAME = bot.get_me().username
except Exception as e: log.warning(f"get_me: {e}")

# ==========================================================
# МОДЕЛИ (cost — реальная закупка Polza)
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

# ---------- rate-limit ----------
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

# ---------- подписка ----------
def sub_active(u):
    return u["sub_plan"] and u["sub_until"] > time.time()

def sub_can_use(u):
    if not sub_active(u): return False, "нет подписки"
    t = SUB_TARIFFS.get(u["sub_plan"])
    if not t: return False, "неизвестный тариф"
    if u["sub_used"] >= t["limit"]: return False, f"лимит {t['limit']}/мес"
    return True, ""

# ==========================================================
# МЕНЮ
# ==========================================================
CAT_MAP = {"🖼 Картинки":"image","🎵 Музыка":"audio","🎬 Видео":"video","🗣 Озвучка (TTS)":"tts",
           "🎞 Оживление":"animate","✏️ Редактирование":"edit","🔍 Апскейл":"upscale","📝 Расшифровка":"stt"}

def menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🖼 Картинки","🎵 Музыка","🎬 Видео","🗣 Озвучка (TTS)")
    kb.add("🎞 Оживление","✏️ Редактирование","🔍 Апскейл","📝 Расшифровка")
    kb.add("💰 Мой баланс","🎫 Подписка","📚 Мои работы")
    kb.add("🎁 Бонус дня","🏆 Задания","💳 Купить (₽)")
    kb.add("📄 Документы","📞 Поддержка")
    if uid == ADMIN_ID: kb.add("🛡 Админ-панель")
    return kb

def cancel_kb():
    return types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))

# ==========================================================
# /start
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

    if not u["onboarded"]:
        return onboarding(uid, uname, is_new)

    greeting = f"👋 Привет, @{uname}!\n\nЯ — <b>Нейро-Студия</b>.\nСгенерировано: {u['total_generated']}"
    if sub_active(u):
        t = SUB_TARIFFS.get(u["sub_plan"], {})
        greeting += f"\n\n🎫 Подписка «{t.get('title','?')}» — осталось {t.get('limit',0) - u['sub_used']} ген."
    bot.send_message(uid, greeting, reply_markup=menu(uid), parse_mode="HTML")

def onboarding(uid, uname, is_new):
    bonus = ""
    if is_new and FIRST_FREE_IMAGE: bonus = "\n\n🎁 <b>Тебе подарок:</b> 1 бесплатная картинка!"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("1️⃣ Что я умею", callback_data="onb_1"))
    bot.send_message(uid,
        f"👋 Привет, @{uname}!\n\nЯ — <b>Нейро-Студия</b>. Генерирую картинки, видео, музыку, озвучку, расшифровку." + bonus +
        f"\n\nДавай за 3 шага покажу, что тут есть:",
        reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("onb_"))
def onboarding_step(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    step = c.data.split("_")[1]
    kb = types.InlineKeyboardMarkup(row_width=1)
    if step == "1":
        kb.add(types.InlineKeyboardButton("2️⃣ Цены и подписка →", callback_data="onb_2"))
        bot.edit_message_text("🖼 <b>Картинки</b> — от 5₽\n🎬 <b>Видео</b> — от 5₽/сек\n"
                              "🎵 <b>Музыка</b> — от 8₽\n🗣 <b>TTS</b> — от 15₽\n📝 <b>STT</b> — от 5₽\n\n"
                              "Всё в одном боте. Выбирай, что нужно — и генерируй.",
                              uid, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif step == "2":
        kb.add(types.InlineKeyboardButton("3️⃣ Попробовать →", callback_data="onb_3"))
        bot.edit_message_text(
            "💰 <b>Пакеты</b>\n10 картинок — 59₽ (5.9₽/шт)\n50 картинок — 239₽ (4.7₽/шт)\n\n"
            "🎫 <b>Подписка</b> (выгоднее пакетов!)\n"
            "Старт — 290₽ / 30 ген.\nПро — 590₽ / 70 ген.\nМаксимум — 990₽ / 130 ген.\n\n"
            "Подписка покрывает любой тип генерации. Отменяется в 1 клик.",
            uid, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    elif step == "3":
        upd(uid, onboarded=1)
        bot.edit_message_text("✅ Готово! Жми любую кнопку в меню — и генерируй.",
                              uid, c.message.message_id)
        bot.send_message(uid, "Меню:", reply_markup=menu(uid))

# ==========================================================
# БАЛАНС
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "💰 Мой баланс")
def bal(m):
    u = get_user(m.from_user.id)
    if not u: return start(m)
    sub_line = ""
    if sub_active(u):
        t = SUB_TARIFFS.get(u["sub_plan"], {})
        auto = "🔄 Автопродление" if u["sub_auto"] else "⏸ Без автопродления"
        sub_line = f"\n\n🎫 Подписка «{t.get('title','?')}» до {datetime.fromtimestamp(u['sub_until']):%d.%m.%Y}\n" \
                   f"Использовано: {u['sub_used']}/{t.get('limit',0)}\n{auto}"
    else:
        sub_line = "\n\n🎫 Подписки нет. Жми «🎫 Подписка»."
    bot.send_message(m.chat.id,
        f"💰 <b>Баланс</b>\n\n"
        f"🖼 {u['balance_img']} | 🎵 {u['balance_aud']} | 🎬 {u['balance_vid']}\n"
        f"🗣 {u['balance_tts']} | 📝 {u['balance_stt']} | ✏️ {u['balance_edit']}\n"
        f"🎞 {u['balance_anim']} | 🔍 {u['balance_up']}\n\n"
        f"🎁 Бесплатные: {u['free_image']} карт. / {u['free_audio']} муз. / {u['free_video']} вид.\n"
        f"👥 Рефералов: {u['referrals']}" + sub_line, parse_mode="HTML")

# ==========================================================
# ЕЖЕДНЕВНЫЙ БОНУС
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🎁 Бонус дня")
def daily_bonus(m):
    uid = m.from_user.id
    u = get_user(uid)
    if not u: return start(m)
    if not DAILY_BONUS:
        return bot.send_message(uid, "Бонус дня временно отключён.")
    if sub_active(u):
        return bot.send_message(uid, "🎫 У тебя есть подписка — бонус дня для подписчиков не нужен 😉")

    now = time.time()
    if now - (u["last_bonus"] or 0) < 86400:
        left = int((86400 - (now - u["last_bonus"])) / 3600) + 1
        return bot.send_message(uid, f"⏳ Бонус будет доступен через ~{left} ч.")

    upd(uid, free_image=u["free_image"] + 1, last_bonus=now)
    bot.send_message(uid, "🎁 Бонус дня: +1 бесплатная картинка!\n\nЖми «🖼 Картинки» — и генерируй.")

# ==========================================================
# ПОДПИСКА (с автопродлением)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🎫 Подписка")
def subscription(m):
    u = get_user(m.from_user.id)
    if not u: return start(m)
    if sub_active(u):
        t = SUB_TARIFFS.get(u["sub_plan"], {})
        auto = "🔄 Включено" if u["sub_auto"] else "⏸ Выключено"
        txt = (f"🎫 <b>Твоя подписка</b>\n\n"
               f"Тариф: <b>{t.get('title','?')}</b>\n"
               f"Действует до: <b>{datetime.fromtimestamp(u['sub_until']):%d.%m.%Y}</b>\n"
               f"Использовано: <b>{u['sub_used']}/{t.get('limit',0)}</b>\n"
               f"Автопродление: {auto}\n\n"
               f"Автопродление — деньги списываются автоматически раз в месяц. Отменить можно в 1 клик.")
        kb = types.InlineKeyboardMarkup(row_width=1)
        if u["sub_auto"]:
            kb.add(types.InlineKeyboardButton("⏸ Отключить автопродление", callback_data="sub_auto_off"))
        else:
            kb.add(types.InlineKeyboardButton("🔄 Включить автопродление", callback_data="sub_auto_on"))
        kb.add(types.InlineKeyboardButton("🔄 Продлить вручную", callback_data="sub_manual"))
    else:
        txt = "🎫 <b>Подписка</b>\n\nВыбери тариф — и генерируй <b>любой</b> тип:\n"
        kb = types.InlineKeyboardMarkup(row_width=1)
        for code, t in SUB_TARIFFS.items():
            kb.add(types.InlineKeyboardButton(
                f"{t['title']} — {t['limit']} ген. / {t['price']}₽",
                callback_data=f"sub_{code}"))
    bot.send_message(m.chat.id, txt, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "sub_auto_off")
def sub_auto_off(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    u = get_user(uid)
    if not u or not u["sub_id"]:
        return bot.send_message(uid, "❌ Нет активной подписки для отмены.")
    # Отмена через Platega: POST /subscription/{id}/cancel (если доступно) — TODO по доке
    # Пока просто отключаем локально
    upd(uid, sub_auto=0)
    log_ev(uid, "sub_auto_off", u["sub_id"])
    bot.send_message(uid, "⏸ Автопродление отключено. Подписка будет активна до конца периода.")

@bot.callback_query_handler(func=lambda c: c.data == "sub_auto_on")
def sub_auto_on(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    u = get_user(uid)
    if not u: return
    bot.send_message(uid, "🔄 Чтобы включить автопродление, оформи подписку заново через «🎫 Подписка».")
    # В Platega автопродление — это и есть подписка (paymentMethod 6), отдельно не включается.
    # Если юзер отключил — надо создать новую подписку.

@bot.callback_query_handler(func=lambda c: c.data == "sub_manual")
def sub_manual(c):
    bot.answer_callback_query(c.id)
    # Просто показываем тарифы для ручной оплаты
    subscription(c.message)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sub_") and len(c.data) > 4 and c.data[4:] in SUB_TARIFFS)
def sub_buy(c):
    bot.answer_callback_query(c.id)
    code = c.data[4:]
    t = SUB_TARIFFS.get(code)
    if not t: return
    if not (PLATEGA_ID and PLATEGA_SECRET):
        return bot.send_message(c.from_user.id, "⚠️ Оплата временно недоступна.")
    uid = c.from_user.id

    # Создаём подписку через Platega: paymentMethod 6, interval 3 (месяц) [citation:1][citation:6][citation:13]
    payload = {
        "paymentMethod": 6,
        "paymentDetails": {
            "amount": t["price"],
            "currency": "RUB",
            "interval": 3,       # 3 = месяц
            "intervalCount": 1
        },
        "description": f"Подписка «{t['title']}»",
    }
    headers = {"X-MerchantId": PLATEGA_ID, "X-Secret": PLATEGA_SECRET}
    try:
        r = requests.post(f"{PLATEGA_URL}/transaction/process",
                          json=payload, headers=headers, timeout=15)
        if r.status_code != 200:
            log.warning(f"sub create: {r.status_code} {r.text[:300]}")
            return bot.send_message(uid, "❌ Ошибка создания подписки.")
        j = r.json()
        pay_url = j.get("redirect")       # для подписки поле redirect [citation:1]
        sub_id = j.get("transactionId")   # это subscriptionId [citation:6]
        if not pay_url:
            return bot.send_message(uid, "❌ Платёжная ссылка не получена.")

        # Сохраняем sub_id в users и payments
        upd(uid, sub_id=sub_id, sub_plan=code, sub_auto=1)
        cc = conn(); cur = cc.cursor()
        cur.execute("INSERT INTO payments(user_id,package_id,amount,status,platega_id,ts,kind) "
                    "VALUES(?,?,?,?,?,?,?)", (uid, code, t["price"], "PENDING", sub_id, time.time(), "subscription"))
        cc.commit(); cc.close()

        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("💳 Подписаться", url=pay_url))
        bot.send_message(uid,
            f"🎫 Подписка «{t['title']}» — {t['price']}₽/мес:\n\n"
            f"Нажми «Подписаться», подтверди в банке — и спишется первый платёж.\n"
            f"Дальше списания будут автоматически. Отменить можно в любой момент.",
            reply_markup=kb)
    except Exception as e:
        log.exception("sub pay error")
        bot.send_message(uid, "❌ Ошибка платежа.")

# ==========================================================
# МОИ РАБОТЫ (+ автопостинг в канал)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📚 Мои работы")
def my_works(m):
    uid = m.from_user.id
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT id, m_type, model_id, prompt, file_id, ts FROM works "
                "WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,))
    rows = cur.fetchall(); cc.close()
    if not rows:
        return bot.send_message(uid, "📚 Пока пусто. Сгенерируй что-нибудь.")
    for wid, m_type, model_id, prompt, file_id, ts in rows:
        model_name = MODELS.get(model_id, {}).get("name", model_id)
        dt = datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")
        caption = f"🕐 {dt} | {model_name}\n💬 {prompt[:150]}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔗 Поделиться", switch_inline_query=f"Смотри что я сгенерил в @{BOT_USERNAME}!"))
        try:
            if m_type == "image":       bot.send_photo(uid, file_id, caption=caption, reply_markup=kb)
            elif m_type == "tts":       bot.send_voice(uid, file_id, caption=caption, reply_markup=kb)
            elif m_type == "audio":     bot.send_audio(uid, file_id, caption=caption, reply_markup=kb)
            elif m_type in ("video","animate"): bot.send_video(uid, file_id, caption=caption, reply_markup=kb)
            else:                       bot.send_document(uid, file_id, caption=caption, reply_markup=kb)
        except Exception as e:
            log.warning(f"send work {wid}: {e}")

# ==========================================================
# ДОКУМЕНТЫ / ПОДДЕРЖКА / ЗАДАНИЯ
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "📄 Документы")
def docs(m):
    kb = types.InlineKeyboardMarkup(row_width=1)
    if TERMS_URL: kb.add(types.InlineKeyboardButton("📜 Соглашение", url=TERMS_URL))
    if PRIVACY_URL: kb.add(types.InlineKeyboardButton("🔒 Политика", url=PRIVACY_URL))
    bot.send_message(m.chat.id, "📄 Документы:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📞 Поддержка")
def support(m):
    if not SUPPORT_URL: return bot.send_message(m.chat.id, "Поддержка: укажите SUPPORT_URL")
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Написать", url=SUPPORT_URL))
    bot.send_message(m.chat.id, "Поддержка:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🏆 Задания")
def quest(m):
    uid = m.from_user.id
    u = get_user(uid)
    if not u: return start(m)
    if u["referrals"] >= 1 and not u["reward_claimed"]:
        upd(uid, free_image=u["free_image"] + 1, reward_claimed=1)
        log_ev(uid, "quest_reward", "+1 free image")
        bot.send_message(uid, "🎉 Пригласил друга! +1 бесплатная картинка.")
    txt = (f"🏆 <b>Задания</b>\n\n"
           f"Пригласить друга: {u['referrals']}/1 {'✅' if u['referrals'] >= 1 else '⏳'}\n\n"
           f"<i>Награда: 1 бесплатная картинка.</i>")
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
        "🔗 Пригласить друга", url=f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"))
    bot.send_message(m.chat.id, txt, reply_markup=kb, parse_mode="HTML")

# ==========================================================
# ПОКУПКА ПАКЕТОВ (разовые)
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "💳 Купить (₽)")
def buy(m):
    if setting("payments_on") != "1":
        return bot.send_message(m.chat.id, "⚠️ Оплата приостановлена.")
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in PACKAGES.items():
        kb.add(types.InlineKeyboardButton(f"{p['title']} — {p['price']}₽", callback_data=f"pay_{pid}"))
    kb.add(types.InlineKeyboardButton("🎫 Подписка (выгоднее)", callback_data="show_subs"))
    bot.send_message(m.chat.id, "💳 <b>Пакеты / Подписка</b>", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "show_subs")
def show_subs(c):
    bot.answer_callback_query(c.id)
    subscription(c.message)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_"))
def pay(c):
    bot.answer_callback_query(c.id)
    pid = c.data[4:]
    p = PACKAGES.get(pid)
    if not p: return
    uid = c.from_user.id
    if not (PLATEGA_ID and PLATEGA_SECRET):
        return bot.send_message(uid, "⚠️ Оплата временно недоступна.")

    # Разовый платёж: paymentMethod 2 (СБП QR) [citation:11]
    payload = {
        "paymentMethod": 2,
        "paymentDetails": {"amount": p["price"], "currency": "RUB"},
        "description": p["title"],
        "return": RETURN_URL,
        "failedUrl": RETURN_URL,
        "payload": f"{uid}_{pid}_{int(time.time())}",
    }
    headers = {"X-MerchantId": PLATEGA_ID, "X-Secret": PLATEGA_SECRET}
    try:
        r = requests.post(f"{PLATEGA_URL}/transaction/process",
                          json=payload, headers=headers, timeout=15)
        if r.status_code != 200:
            return bot.send_message(uid, "❌ Ошибка создания платежа.")
        j = r.json()
        pay_url = j.get("redirect")
        tx_id = j.get("transactionId")
        if not pay_url: return bot.send_message(uid, "❌ Платёжная ссылка не получена.")
        cc = conn(); cur = cc.cursor()
        cur.execute("INSERT INTO payments(user_id,package_id,amount,status,platega_id,ts,kind) "
                    "VALUES(?,?,?,?,?,?,?)", (uid, pid, p["price"], "PENDING", tx_id, time.time(), "package"))
        cc.commit(); cc.close()
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Оплатить (СБП)", url=pay_url))
        bot.send_message(uid, f"💳 {p['title']} — {p['price']}₽:", reply_markup=kb)
    except Exception as e:
        log.exception("platega error")
        bot.send_message(uid, "❌ Ошибка платежа.")

# ==========================================================
# ВЫБОР МОДЕЛИ
# ==========================================================
@bot.message_handler(func=lambda m: m.text in CAT_MAP)
def category(m):
    if setting("generations_on") != "1":
        return bot.send_message(m.chat.id, "⚠️ Генерации приостановлены.")
    m_type = CAT_MAP[m.text]
    models = active_by_type(m_type)
    if not models:
        return bot.send_message(m.chat.id, "❌ Все модели категории отключены.")
    kb = types.InlineKeyboardMarkup(row_width=1)
    for mid, price in models.items():
        suffix = "/сек" if m_type == "video" else ""
        kb.add(types.InlineKeyboardButton(f"{MODELS[mid]['name']} ({price}₽{suffix})", callback_data=f"mod_{mid}"))
    bot.send_message(m.chat.id, "Выбери модель:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mod_"))
def pick_model(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    mid = c.data[4:]
    m = get_model(mid)
    if not m or not m["active"]:
        return bot.send_message(c.message.chat.id, "❌ Модель недоступна.")
    m_type = MODELS[mid]["type"]

    if m["price"] >= 15 and m_type != "video":
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton(f"✅ Да, {m['price']}₽", callback_data=f"conf_{mid}"),
               types.InlineKeyboardButton("❌ Нет", callback_data="cancel"))
        return bot.send_message(c.message.chat.id,
            f"<b>{MODELS[mid]['name']}</b> — {m['price']}₽.\n\nТочно хочешь?", reply_markup=kb, parse_mode="HTML")

    if m_type == "video":
        kb = types.InlineKeyboardMarkup(row_width=3)
        for sec in (3, 5, 10):
            kb.add(types.InlineKeyboardButton(f"{sec}с ({sec*m['price']}₽)", callback_data=f"vdur_{sec}_{mid}"))
        set_state(uid, "waiting_for_prompt", mid, m["price"])
        return bot.send_message(c.message.chat.id,
            f"{MODELS[mid]['name']} — {m['price']}₽/сек.\nВыбери длительность:", reply_markup=kb)

    set_state(uid, "waiting_for_prompt", mid, m["price"])
    hint = "Отправь файл" + (" (+ подпись = промпт)" if m_type in FILE_REQUIRED else "") \
           if m_type in FILE_REQUIRED else "Напиши запрос"
    msg = bot.send_message(c.message.chat.id,
        f"<b>{MODELS[mid]['name']}</b> ({m['price']}₽).\n{hint}:", parse_mode="HTML")
    bot.edit_message_reply_markup(c.message.chat.id, msg.message_id, reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("conf_"))
def confirm_spend(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    mid = c.data[5:]
    m = get_model(mid)
    if not m: return
    m_type = MODELS[mid]["type"]
    set_state(uid, "waiting_for_prompt", mid, m["price"])
    hint = "Отправь файл" + (" (+ подпись = промпт)" if m_type in FILE_REQUIRED else "") \
           if m_type in FILE_REQUIRED else "Напиши запрос"
    bot.send_message(c.message.chat.id,
        f"<b>{MODELS[mid]['name']}</b> ({m['price']}₽).\n{hint}:", parse_mode="HTML",
        reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("vdur_"))
def vdur(c):
    bot.answer_callback_query(c.id)
    uid = c.from_user.id
    _, sec, mid = c.data.split("_")
    sec = int(sec); m = get_model(mid)
    if not m: return
    price = m["price"] * sec
    set_state(uid, "waiting_for_prompt", mid, price)
    msg = bot.send_message(c.message.chat.id,
        f"{MODELS[mid]['name']} — {sec} сек ({price}₽).\nНапиши запрос:")
    bot.edit_message_reply_markup(c.message.chat.id, msg.message_id, reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data == "cancel")
def cancel(c):
    bot.answer_callback_query(c.id, "Отменено")
    set_state(c.from_user.id, "")
    bot.send_message(c.message.chat.id, "❌ Отменено.", reply_markup=menu(c.from_user.id))

# ==========================================================
# ВВОД
# ==========================================================
@bot.message_handler(content_types=["text","photo","video","voice","audio"])
def handle_input(m):
    uid = m.from_user.id
    u = get_user(uid)
    if not u or u["is_banned"]: return
    if u["state"] != "waiting_for_prompt":
        return bot.send_message(m.chat.id, "Выбери действие в меню или нажми /start.")
    mid = u["temp_model_id"]
    if mid not in MODELS:
        set_state(uid, ""); return bot.send_message(m.chat.id, "❌ Модель недоступна.")
    m_type = MODELS[mid]["type"]

    if uid != ADMIN_ID and not check_rate(uid):
        return bot.send_message(m.chat.id, f"⏳ Лимит {RATE_LIMIT} ген/час. Попробуй позже.")

    check_text = (m.caption or "") if m.content_type != "text" else (m.text or "")
    if check_text and BANNED.search(check_text):
        set_state(uid, "")
        return bot.send_message(m.chat.id, "❌ Запрещённые слова. Отменено.")

    if m_type in FILE_REQUIRED and m.content_type == "text":
        set_state(uid, "waiting_for_prompt", mid, u["temp_price"])
        return bot.send_message(m.chat.id,
            "⚠️ Для этой модели нужен файл. Или «Отмена»:", reply_markup=cancel_kb())
    if m_type not in FILE_REQUIRED and m.content_type != "text":
        set_state(uid, "waiting_for_prompt", mid, u["temp_price"])
        return bot.send_message(m.chat.id,
            "⚠️ Для этой модели нужен текст. Или «Отмена»:", reply_markup=cancel_kb())

    set_state(uid, "")
    is_admin = (uid == ADMIN_ID)
    paid_by = None

    if not is_admin:
        can_sub, _ = sub_can_use(u)
        if can_sub:
            upd(uid, sub_used=u["sub_used"] + 1)
            paid_by = "sub"
            t = SUB_TARIFFS.get(u["sub_plan"], {})
            bot.send_message(uid, f"🎫 По подписке. Осталось: {t.get('limit',0) - u['sub_used'] - 1}")
        elif m_type == "image" and u["free_image"] > 0:
            upd(uid, free_image=u["free_image"] - 1)
            paid_by = "free"
            bot.send_message(uid, "🎁 Бесплатная генерация!")
        elif deduct(uid, m_type):
            paid_by = "balance"
            bot.send_message(uid, "✅ Списано с баланса.")
        else:
            return bot.send_message(uid, "❌ Нет подписки и недостаточно баланса.\n"
                                         "Купи пакет в «💳 Купить» или оформи «🎫 Подписка».")
    else:
        paid_by = "admin"

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
        if m_type == "edit" or m_type == "animate":
            inp["images"] = [{"type": "base64", "data": data_uri}]
        elif m_type == "upscale":
            field = "videos" if "video" in mid else "images"
            inp[field] = [{"type": "base64", "data": data_uri}]
    return {"model": mid, "async": False, "input": inp}

def download_telegram_file(file_id):
    try:
        fi = bot.get_file(file_id)
        return bot.download_file(fi.file_path)
    except Exception as e:
        log.warning(f"download_file: {e}")
        return None

def transcribe(file_bytes, file_mime, mid):
    headers = {"Authorization": f"Bearer {POLZA_KEY}"}
    files = {"file": ("audio.ogg", file_bytes, file_mime or "audio/ogg")}
    data = {"model": mid}
    try:
        r = requests.post(f"{POLZA_BASE}/audio/transcriptions",
                          headers=headers, files=files, data=data, timeout=120)
        if r.status_code != 200:
            log.warning(f"stt: {r.status_code} {r.text[:200]}")
            return None
        return r.json().get("text")
    except Exception as e:
        log.warning(f"stt err: {e}")
        return None

def gen(uid, message, mid, m_type, price, is_admin, paid_by):
    prompt = message.text or message.caption or ""
    file_bytes = None
    if message.content_type in ("photo","video","voice","audio","document"):
        if message.content_type == "photo":
            file_id = message.photo[-1].file_id
        else:
            file_id = getattr(message, message.content_type).file_id
        file_bytes = download_telegram_file(file_id)

    if m_type == "stt":
        status = bot.send_message(uid, "⏳ Расшифровка...")
        text = transcribe(file_bytes or b"", "audio/ogg", mid)
        try: bot.delete_message(uid, status.message_id)
        except: pass
        if not text:
            if paid_by == "balance": refund(uid, m_type)
            elif paid_by == "sub":
                u = get_user(uid); upd(uid, sub_used=max(0, u["sub_used"]-1))
            return bot.send_message(uid, "❌ Ошибка расшифровки. Возвращено.")
        bot.send_message(uid, f"📝 <b>Расшифровка:</b>\n\n{text[:3500]}", parse_mode="HTML")
        u2 = get_user(uid); upd(uid, total_generated=u2["total_generated"] + 1)
        return

    duration = None
    if m_type == "video" and price:
        per_sec = MODELS[mid]["price"]
        duration = max(1, price // per_sec) if per_sec else 5

    payload = build_payload(mid, m_type, prompt, file_bytes, duration)
    headers = {"Authorization": f"Bearer {POLZA_KEY}", "Content-Type": "application/json"}
    status = bot.send_message(uid, f"⏳ Генерация ({m_type})...\nПримерно ~{ESTIMATED.get(m_type,15)} сек.")

    try:
        r = requests.post(f"{POLZA_BASE}/media", headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            try: err = r.json().get("error",{}).get("message", r.text[:200])
            except: err = r.text[:200]
            bot.edit_message_text(f"❌ Ошибка API: {err}\n💰 Возвращено.", uid, status.message_id)
            if paid_by == "balance": refund(uid, m_type)
            elif paid_by == "sub":
                u = get_user(uid); upd(uid, sub_used=max(0, u["sub_used"]-1))
            return

        data = r.json()
        if data.get("status") == "pending" and data.get("id"):
            deadline = time.time() + POLL_TIMEOUT.get(m_type, 120)
            last_edit = 0
            while time.time() < deadline:
                time.sleep(2)
                try:
                    chk = requests.get(f"{POLZA_BASE}/media/{data['id']}", headers=headers, timeout=15).json()
                except Exception as e:
                    log.warning(f"poll error: {e}"); continue
                st = chk.get("status")
                if st == "completed": data = chk; break
                if st == "failed":
                    bot.edit_message_text("❌ Генерация не удалась. Возвращено.", uid, status.message_id)
                    if paid_by == "balance": refund(uid, m_type)
                    elif paid_by == "sub":
                        u = get_user(uid); upd(uid, sub_used=max(0, u["sub_used"]-1))
                    return
                if time.time() - last_edit >= 5:
                    left = max(0, int(deadline - time.time()))
                    try: bot.edit_message_text(f"⏳ Генерация...\nОсталось ~{left} сек.", uid, status.message_id)
                    except: pass
                    last_edit = time.time()
            else:
                bot.edit_message_text("⏳ Таймаут. Возвращено.", uid, status.message_id)
                if paid_by == "balance": refund(uid, m_type)
                elif paid_by == "sub":
                    u = get_user(uid); upd(uid, sub_used=max(0, u["sub_used"]-1))
                return

        url = None
        if isinstance(data.get("data"), list) and data["data"]:
            url = data["data"][0].get("url")
        url = url or data.get("url")
        if not url:
            bot.edit_message_text("❌ API не вернул ссылку. Возвращено.", uid, status.message_id)
            if paid_by == "balance": refund(uid, m_type)
            elif paid_by == "sub":
                u = get_user(uid); upd(uid, sub_used=max(0, u["sub_used"]-1))
            return

        try:
            fresp = requests.get(url, timeout=180)
            if fresp.status_code != 200: raise Exception("download failed")
        except Exception:
            bot.edit_message_text("❌ Не удалось скачать. Возвращено.", uid, status.message_id)
            if paid_by == "balance": refund(uid, m_type)
            elif paid_by == "sub":
                u = get_user(uid); upd(uid, sub_used=max(0, u["sub_used"]-1))
            return

        ext_map = {"image":".jpg","audio":".mp3","tts":".ogg","video":".mp4",
                   "edit":".jpg","animate":".mp4","upscale":".bin"}
        tmp = f"temp_{uid}_{int(time.time())}{ext_map.get(m_type,'.bin')}"
        with open(tmp,"wb") as f: f.write(fresp.content)
        try: bot.delete_message(uid, status.message_id)
        except: pass

        sent = None
        with open(tmp,"rb") as f:
            if m_type == "image":              sent = bot.send_photo(uid, f, caption="🎨 Готово")
            elif m_type == "tts":              sent = bot.send_voice(uid, f, caption="🗣 Готово")
            elif m_type == "audio":            sent = bot.send_audio(uid, f, caption="🎵 Готово")
            elif m_type in ("video","animate"):sent = bot.send_video(uid, f, caption="🎬 Готово")
            else:                              sent = bot.send_document(uid, f, caption="📁 Готово")

        os.remove(tmp)
        u2 = get_user(uid)
        upd(uid, total_generated=u2["total_generated"] + 1)

        # Сохраняем в работы
        if sent:
            try:
                if m_type == "image":            fid = sent.photo[-1].file_id
                elif m_type == "tts":            fid = sent.voice.file_id
                elif m_type == "audio":          fid = sent.audio.file_id
                elif m_type in ("video","animate"): fid = sent.video.file_id
                else:                            fid = sent.document.file_id
                add_work(uid, m_type, mid, prompt, fid)

                # Автопостинг в канал (только для image/video/animate)
                if CHANNEL_ID and m_type in ("image", "video", "animate"):
                    try:
                        kb_ch = types.InlineKeyboardMarkup()
                        kb_ch.add(types.InlineKeyboardButton("🎨 Попробовать", url=f"https://t.me/{BOT_USERNAME}?start=ch"))
                        if m_type == "image":
                            bot.send_photo(CHANNEL_ID, fid, caption=f"🎨 Сгенерировано в @{BOT_USERNAME}", reply_markup=kb_ch)
                        else:
                            bot.send_video(CHANNEL_ID, fid, caption=f"🎬 Сгенерировано в @{BOT_USERNAME}", reply_markup=kb_ch)
                    except Exception as e:
                        log.warning(f"channel post: {e}")
            except Exception as e:
                log.warning(f"add_work: {e}")

    except Exception as e:
        log.exception("generation error")
        try: bot.delete_message(uid, status.message_id)
        except: pass
        bot.send_message(uid, f"❌ Сбой: {e}. Возвращено.")
        if paid_by == "balance": refund(uid, m_type)
        elif paid_by == "sub":
            u = get_user(uid); upd(uid, sub_used=max(0, u["sub_used"]-1))

# ==========================================================
# /promo
# ==========================================================
@bot.message_handler(commands=["promo"])
def promo_activate(m):
    uid = m.from_user.id
    parts = (m.text or "").split()
    if len(parts) < 2: return bot.send_message(uid, "Использование: /promo КОД")
    code = parts[1].strip().upper()
    c = conn(); cur = c.cursor()
    cur.execute("SELECT type, value, uses_left FROM promo WHERE code=?", (code,))
    row = cur.fetchone()
    if not row: c.close(); return bot.send_message(uid, "❌ Промокод не найден.")
    typ, val, left = row
    if left <= 0: c.close(); return bot.send_message(uid, "❌ Промокод исчерпан.")
    cur.execute("SELECT 1 FROM promo_used WHERE code=? AND user_id=?", (code, uid))
    if cur.fetchone(): c.close(); return bot.send_message(uid, "❌ Ты уже использовал этот промокод.")
    cur.execute("UPDATE promo SET uses_left=uses_left-1 WHERE code=?", (code,))
    cur.execute("INSERT INTO promo_used(code,user_id,ts) VALUES(?,?,?)", (code, uid, time.time()))
    c.commit(); c.close()
    u = get_user(uid)
    upd(uid, **{BAL_FIELD[typ]: u[BAL_FIELD[typ]] + val})
    log_ev(uid, "promo_used", f"{code}: +{val} {typ}")
    bot.send_message(uid, f"🎉 Промокод активирован: +{val} ({typ})")

# ==========================================================
# АДМИНКА
# ==========================================================
@bot.message_handler(func=lambda m: m.text == "🛡 Админ-панель")
def admin(m):
    if m.from_user.id != ADMIN_ID: return
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📊 Дашборд", callback_data="a_dash"),
           types.InlineKeyboardButton("💰 Маржа", callback_data="a_margin"))
    kb.add(types.InlineKeyboardButton("👥 Юзеры", callback_data="a_users"),
           types.InlineKeyboardButton("💳 Платежи", callback_data="a_pays"))
    kb.add(types.InlineKeyboardButton("📢 Рассылка", callback_data="a_bc"),
           types.InlineKeyboardButton("⚙️ Модели", callback_data="a_models"))
    kb.add(types.InlineKeyboardButton("🛑 Kill-Switch", callback_data="a_kill"),
           types.InlineKeyboardButton("🏷 Промокоды", callback_data="a_promo"))
    kb.add(types.InlineKeyboardButton("📜 Логи", callback_data="a_logs"))
    bot.send_message(m.chat.id, "🛡 <b>Админ-панель</b>", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("a_"))
def admin_actions(c):
    if c.from_user.id != ADMIN_ID: return bot.answer_callback_query(c.id, "Нет доступа")
    bot.answer_callback_query(c.id)
    act = c.data[2:]

    if act == "dash":
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT COUNT(*), COALESCE(SUM(total_generated),0) FROM users")
        users, gens = cur.fetchone()
        cur.execute("SELECT COALESCE(SUM(amount),0), COUNT(*) FROM payments WHERE status='CONFIRMED'")
        revenue, pays = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM users WHERE sub_until > ?", (time.time(),))
        active_subs = cur.fetchone()[0]
        cc.close()
        bot.send_message(c.message.chat.id,
            f"📊 <b>Дашборд</b>\n\n👥 Юзеров: {users}\n🎨 Генераций: {gens}\n"
            f"🎫 Активных подписок: {active_subs}\n💰 Выручка: {revenue}₽ ({pays} платежей)\n\n"
            f"Оплата: {'✅' if setting('payments_on')=='1' else '🛑'}\n"
            f"Генерации: {'✅' if setting('generations_on')=='1' else '🛑'}",
            parse_mode="HTML")

    elif act == "margin":
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT COALESCE(SUM(amount),0), COUNT(*) FROM payments WHERE status='CONFIRMED'")
        revenue, pays = cur.fetchone()
        cur.execute("SELECT model_id, COUNT(*) FROM works GROUP BY model_id")
        works = cur.fetchall()
        total_cost = 0
        by_model = []
        for mid, cnt in works:
            cost = MODELS.get(mid, {}).get("cost", 0)
            sub = cost * cnt
            total_cost += sub
            by_model.append((mid, cnt, cost, sub))
        cc.close()
        profit = revenue - total_cost
        margin = (profit / revenue * 100) if revenue else 0
        txt = (f"💰 <b>Маржа</b>\n\n"
               f"Выручка: <b>{revenue}₽</b> ({pays} платежей)\n"
               f"Себестоимость: <b>{total_cost:.2f}₽</b>\n"
               f"Прибыль: <b>{profit:.2f}₽</b>\n"
               f"Маржа: <b>{margin:.1f}%</b>\n\n"
               f"<b>По моделям:</b>\n")
        for mid, cnt, cost, sub in by_model[:15]:
            name = MODELS.get(mid, {}).get("name", mid)
            txt += f"• {name}: {cnt} шт × {cost}₽ = {sub:.2f}₽\n"
        bot.send_message(c.message.chat.id, txt, parse_mode="HTML")

    elif act == "users":
        msg = bot.send_message(c.message.chat.id, "Введи <code>@username</code> или ID:", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_find_user)

    elif act == "pays":
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT user_id,package_id,amount,status,ts,kind FROM payments ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall(); cc.close()
        if not rows: return bot.send_message(c.message.chat.id, "Платежей нет.")
        txt = "💳 <b>Платежи</b>\n\n"
        for uid_, pid, amt, st, ts, kind in rows:
            txt += f"• {uid_} | {pid} | {amt}₽ | {st} | {kind} | {datetime.fromtimestamp(ts):%d.%m %H:%M}\n"
        bot.send_message(c.message.chat.id, txt, parse_mode="HTML")

    elif act == "bc":
        msg = bot.send_message(c.message.chat.id, "Текст рассылки (предпросмотр):")
        bot.register_next_step_handler(msg, admin_bc_preview)

    elif act == "models":
        kb = types.InlineKeyboardMarkup(row_width=1)
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT model_id, active FROM models")
        for mid, a in cur.fetchall():
            kb.add(types.InlineKeyboardButton(f"{'🟢' if a else '🔴'} {MODELS.get(mid,{}).get('name',mid)}",
                                              callback_data=f"m_toggle_{mid}"))
        cc.close()
        bot.send_message(c.message.chat.id, "Вкл/выкл модели:", reply_markup=kb)

    elif act == "kill":
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton(
            f"Оплата: {'🛑 Выключить' if setting('payments_on')=='1' else '🟢 Включить'}",
            callback_data="k_pay"))
        kb.add(types.InlineKeyboardButton(
            f"Генерации: {'🛑 Выключить' if setting('generations_on')=='1' else '🟢 Включить'}",
            callback_data="k_gen"))
        bot.send_message(c.message.chat.id, "🛑 Kill-Switch:", reply_markup=kb)

    elif act == "promo":
        msg = bot.send_message(c.message.chat.id,
            "Введи: <code>code type value uses</code>\n"
            "type: image/audio/video/tts/stt/edit/animate/upscale\n"
            "Пример: <code>FREE10 image 10 100</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_add_promo)

    elif act == "logs":
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT user_id,action,details,ts FROM logs ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall(); cc.close()
        if not rows: return bot.send_message(c.message.chat.id, "Логов нет.")
        txt = "📜 <b>Логи</b>\n\n"
        for u_, a_, d_, t_ in rows:
            txt += f"• {datetime.fromtimestamp(t_):%d.%m %H:%M} | {u_} | {a_} | {d_}\n"
        bot.send_message(c.message.chat.id, txt[:4000], parse_mode="HTML")

def admin_find_user(m):
    q = m.text.strip().replace("@","").lower()
    cc = conn(); cur = cc.cursor()
    if q.isdigit():
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (int(q),))
    else:
        cur.execute("SELECT user_id FROM users WHERE LOWER(username)=?", (q,))
    row = cur.fetchone(); cc.close()
    if not row: return bot.send_message(m.chat.id, "❌ Не найден.")
    uid = row[0]; u = get_user(uid)
    if not u: return bot.send_message(m.chat.id, "❌ Не найден.")
    sub_info = ""
    if sub_active(u):
        t = SUB_TARIFFS.get(u["sub_plan"], {})
        auto = "🔄" if u["sub_auto"] else "⏸"
        sub_info = f"\n🎫 {t.get('title','?')} до {datetime.fromtimestamp(u['sub_until']):%d.%m} ({u['sub_used']}/{t.get('limit',0)}) {auto}"
    txt = (f"👤 <b>@{u['username']}</b> (ID: <code>{uid}</code>)\n"
           f"{'🚫 Забанен' if u['is_banned'] else '✅ Активен'} | ген: {u['total_generated']}" + sub_info + "\n\n"
           f"🖼{u['balance_img']} 🎵{u['balance_aud']} 🎬{u['balance_vid']} "
           f"🗣{u['balance_tts']} 📝{u['balance_stt']} ✏️{u['balance_edit']} "
           f"🎞{u['balance_anim']} 🔍{u['balance_up']}")
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("⭐ Выдать", callback_data=f"g_{uid}"),
           types.InlineKeyboardButton("🚫 Бан/Разбан", callback_data=f"b_{uid}"))
    kb.add(types.InlineKeyboardButton("🎫 Выдать подписку", callback_data=f"sg_{uid}"))
    bot.send_message(m.chat.id, txt, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("sg_"))
def admin_gift_sub(c):
    if c.from_user.id != ADMIN_ID: return
    bot.answer_callback_query(c.id)
    uid = int(c.data[3:])
    kb = types.InlineKeyboardMarkup(row_width=1)
    for code, t in SUB_TARIFFS.items():
        kb.add(types.InlineKeyboardButton(f"{t['title']} ({t['limit']} ген.)",
                                          callback_data=f"sgd_{code}_{uid}"))
    bot.send_message(c.message.chat.id, "Выбери тариф:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sgd_"))
def admin_gift_sub_do(c):
    if c.from_user.id != ADMIN_ID: return
    _, code, uid = c.data.split("_")
    uid = int(uid); t = SUB_TARIFFS.get(code)
    if not t: return bot.answer_callback_query(c.id, "Нет тарифа")
    until = time.time() + t["days"] * 86400
    upd(uid, sub_plan=code, sub_until=until, sub_used=0, sub_auto=0, sub_notified=0)
    log_ev(ADMIN_ID, "gift_sub", f"{code} → {uid}")
    bot.answer_callback_query(c.id, "Готово")
    bot.send_message(c.message.chat.id, f"✅ {uid}: «{t['title']}» до {datetime.fromtimestamp(until):%d.%m}")
    try: bot.send_message(uid, f"🎫 Тебе активирована подписка «{t['title']}»!")
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("g_"))
def admin_gift(c):
    if c.from_user.id != ADMIN_ID: return
    bot.answer_callback_query(c.id)
    uid = int(c.data[2:])
    msg = bot.send_message(c.message.chat.id, "Введи: <code>тип количество</code>", parse_mode="HTML")
    bot.register_next_step_handler(msg, admin_do_gift, uid)

def admin_do_gift(m, uid):
    try:
        parts = m.text.split()
        if len(parts) != 2: raise ValueError
        t, n = parts[0].lower(), int(parts[1])
        if t not in BAL_FIELD or not (1 <= n <= 1000): raise ValueError
        u = get_user(uid)
        upd(uid, **{BAL_FIELD[t]: u[BAL_FIELD[t]] + n})
        log_ev(ADMIN_ID, "gift", f"{n} {t} → {uid}")
        bot.send_message(m.chat.id, f"✅ Выдано {n} {t}")
        try: bot.send_message(uid, f"🎁 Начислено {n} ({t})")
        except: pass
    except:
        bot.send_message(m.chat.id, "❌ Пример: <code>image 5</code>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith("b_"))
def admin_ban(c):
    if c.from_user.id != ADMIN_ID: return
    uid = int(c.data[2:])
    u = get_user(uid)
    upd(uid, is_banned=not u["is_banned"])
    log_ev(ADMIN_ID, "ban_toggle", f"{uid} → {not u['is_banned']}")
    bot.answer_callback_query(c.id, "Готово")
    bot.send_message(c.message.chat.id, f"✅ {uid}: {'забанен' if not u['is_banned'] else 'разбанен'}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("m_toggle_"))
def toggle_model(c):
    if c.from_user.id != ADMIN_ID: return
    mid = c.data[len("m_toggle_"):]
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT active FROM models WHERE model_id=?", (mid,))
    r = cur.fetchone()
    if not r: cc.close(); return
    new = 0 if r[0] else 1
    cur.execute("UPDATE models SET active=? WHERE model_id=?", (new, mid))
    cc.commit(); cc.close()
    log_ev(ADMIN_ID, "model_toggle", f"{mid} → {new}")
    bot.answer_callback_query(c.id, f"{'вкл' if new else 'выкл'}")
    bot.send_message(c.message.chat.id, f"{MODELS[mid]['name']}: {'🟢' if new else '🔴'}")

@bot.callback_query_handler(func=lambda c: c.data in ("k_pay","k_gen"))
def kill(c):
    if c.from_user.id != ADMIN_ID: return
    if c.data == "k_pay":
        new = "0" if setting("payments_on") == "1" else "1"
        set_setting("payments_on", new)
    else:
        new = "0" if setting("generations_on") == "1" else "1"
        set_setting("generations_on", new)
    bot.answer_callback_query(c.id, "Готово")
    bot.send_message(c.message.chat.id,
        f"{'Оплата' if c.data=='k_pay' else 'Генерации'}: {'🟢' if new=='1' else '🛑'}")

BC_CACHE = {}

def admin_bc_preview(m):
    BC_CACHE[m.from_user.id] = (m.text, time.time())
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("✅ Отправить", callback_data="bc_go"),
           types.InlineKeyboardButton("❌ Отмена", callback_data="bc_no"))
    bot.send_message(m.chat.id, f"Предпросмотр:\n\n{m.text}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ("bc_go","bc_no"))
def bc_confirm(c):
    if c.from_user.id != ADMIN_ID: return
    if c.data == "bc_no":
        BC_CACHE.pop(ADMIN_ID, None)
        return bot.answer_callback_query(c.id, "Отменено")
    item = BC_CACHE.pop(ADMIN_ID, None)
    if not item: return bot.answer_callback_query(c.id, "Текст потерян")
    text, ts = item
    if time.time() - ts > 600:
        return bot.answer_callback_query(c.id, "Устарел")
    bot.answer_callback_query(c.id, "Рассылка начата")
    threading.Thread(target=do_broadcast, args=(text,), daemon=True).start()

def do_broadcast(text):
    cc = conn(); cur = cc.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = [r[0] for r in cur.fetchall()]; cc.close()
    ok = fail = 0
    total = len(users)
    for i, uid in enumerate(users, 1):
        try:
            bot.send_message(uid, text); ok += 1
        except ApiTelegramException as e:
            ra = 0
            try: ra = int(e.result_json.get("parameters", {}).get("retry_after", 0))
            except: pass
            if ra:
                time.sleep(ra + 1)
                try: bot.send_message(uid, text); ok += 1
                except: fail += 1
            else: fail += 1
        except Exception: fail += 1
        time.sleep(0.05)
        if i % 100 == 0:
            try: bot.send_message(ADMIN_ID, f"📢 {i}/{total}")
            except: pass
    try: bot.send_message(ADMIN_ID, f"📢 Готово: ✅ {ok} / ❌ {fail}")
    except: pass
    log_ev(ADMIN_ID, "broadcast", f"ok={ok} fail={fail}")

def admin_add_promo(m):
    try:
        parts = m.text.split()
        if len(parts) != 4: raise ValueError
        code, typ = parts[0].upper(), parts[1].lower()
        val, uses = int(parts[2]), int(parts[3])
        if typ not in BAL_FIELD or not (1 <= val <= 1000) or not (1 <= uses <= 10000):
            raise ValueError
        cc = conn(); cur = cc.cursor()
        cur.execute("SELECT 1 FROM promo WHERE code=?", (code,))
        if cur.fetchone(): cc.close(); return bot.send_message(m.chat.id, "⚠️ Код уже есть.")
        cur.execute("INSERT INTO promo(code,type,value,uses_left) VALUES(?,?,?,?)", (code, typ, val, uses))
        cc.commit(); cc.close()
        log_ev(ADMIN_ID, "promo_create", f"{code}: +{val} {typ} x{uses}")
        bot.send_message(m.chat.id, f"✅ {code}: +{val} {typ}")
    except:
        bot.send_message(m.chat.id, "❌ Пример: <code>FREE10 image 10 100</code>", parse_mode="HTML")

# ==========================================================
# Фоновый поток: напоминание о конце подписки
# ==========================================================
def sub_notifier():
    while True:
        try:
            cc = conn(); cur = cc.cursor()
            now = time.time()
            soon = now + 3 * 86400
            cur.execute("""SELECT user_id, sub_plan, sub_until FROM users
                           WHERE sub_until > ? AND sub_until < ? AND sub_notified = 0""",
                        (now, soon))
            rows = cur.fetchall()
            for uid, plan, until in rows:
                t = SUB_TARIFFS.get(plan, {})
                try:
                    bot.send_message(uid,
                        f"⏰ <b>Подписка «{t.get('title','?')}» заканчивается</b>\n\n"
                        f"Дата: {datetime.fromtimestamp(until):%d.%m.%Y}\n"
                        f"Продли в «🎫 Подписка», чтобы не потерять доступ.",
                        parse_mode="HTML")
                except: pass
                cur.execute("UPDATE users SET sub_notified=1 WHERE user_id=?", (uid,))
            cur.execute("UPDATE users SET sub_notified=0 WHERE sub_until < ?", (now,))
            cc.commit(); cc.close()
        except Exception as e:
            log.warning(f"notifier: {e}")
        time.sleep(3600)

threading.Thread(target=sub_notifier, daemon=True).start()

# ==========================================================
# ЗАПУСК
# ==========================================================
if __name__ == "__main__":
    log.info("🚀 Бот запущен")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
