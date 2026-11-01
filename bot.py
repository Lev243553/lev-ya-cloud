import telebot
from telebot import types
import requests
import time
import os
import sqlite3
import threading

# --- НАСТРОЙКИ ---
TOKEN = "8959456335:AAFmQZmvsWuma4U0TZhIpBQJ8Kd2VOHwRN8" 
POLZA_API_KEY = "pza_qGQO8ZXtNks1OxNxKOGjd-Y01K9i-E0g"
API_URL = "https://polza.ai/api/v1/media"
ADMIN_ID = 7031603236
DB_PATH = "media_bot.db"

PRIVACY_URL = "https://telegra.ph/politika-konfidencialnosti-plamenureralbot-11-01"
TERMS_URL = "https://telegra.ph/polzovatelskoe-soglashenie-plamenureralbot-11-01-2"

bot = telebot.TeleBot(TOKEN, threaded=True)

# ... (Словари MODEL_NAMES, MODEL_TYPES, MODEL_PRICES_RUB остаются без изменений) ...
MODEL_NAMES = {
    "openai/gpt-image-1.5": "GPT Image 1.5", "openai/gpt-5-image": "GPT-5 Image",
    "google/gemini-2.5-flash-image": "Gemini 2.5 Flash", "google/gemini-3.1-flash-lite-image": "Gemini 3.1 Lite",
    "google/gemini-nano-banana-2.1": "Nano Banana 2.1", "black-forest-labs/flux.2-flex": "Flux 2 Flex",
    "bytedance/seedream-4": "Seedream 4", "bytedance/seedream-5-lite": "Seedream 5 Lite",
    "qwen/image": "Qwen Image", "tongyi-mai/z-image": "Tongyi Z-Image", "yandex/yandex-art": "Yandex Art",
    "google/lyria-3-pro-preview": "Lyria 3 Pro", "suno/sounds": "Suno Sounds", "google/lyria-3-clip-preview": "Lyria 3 Clip"
}
MODEL_TYPES = {
    "openai/gpt-image-1.5": "image", "openai/gpt-5-image": "image", "google/gemini-2.5-flash-image": "image",
    "google/gemini-3.1-flash-lite-image": "image", "google/gemini-nano-banana-2.1": "image", "black-forest-labs/flux.2-flex": "image",
    "bytedance/seedream-4": "image", "bytedance/seedream-5-lite": "image", "qwen/image": "image", "tongyi-mai/z-image": "image",
    "yandex/yandex-art": "image", "google/lyria-3-pro-preview": "audio", "suno/sounds": "audio", "google/lyria-3-clip-preview": "audio"
}
MODEL_PRICES_RUB = {
    "openai/gpt-image-1.5": 20, "openai/gpt-5-image": 25, "google/gemini-2.5-flash-image": 15,
    "google/gemini-3.1-flash-lite-image": 10, "google/gemini-nano-banana-2.1": 10, "black-forest-labs/flux.2-flex": 20,
    "bytedance/seedream-4": 15, "bytedance/seedream-5-lite": 10, "qwen/image": 10, "tongyi-mai/z-image": 10,
    "yandex/yandex-art": 10, "google/lyria-3-pro-preview": 25, "suno/sounds": 10, "google/lyria-3-clip-preview": 15
}

user_data = {}
promo_active = False

# ==========================================
# 1. БАЗА ДАННЫХ
# ==========================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, is_banned INTEGER DEFAULT 0, 
        total_generated INTEGER DEFAULT 0, free_image INTEGER DEFAULT 0, free_audio INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    # НОВАЯ ТАБЛИЦА ДЛЯ ОТЛОЖЕННЫХ ПОДАРКОВ
    c.execute('''CREATE TABLE IF NOT EXISTS pending_gifts (
        username TEXT PRIMARY KEY, free_image INTEGER DEFAULT 0, free_audio INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    
    global promo_active
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'promo_active'")
    row = c.fetchone()
    if row: promo_active = (row[0] == '1')
    conn.close()

init_db()

def db_get_user(user_id):
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT username, is_banned, total_generated, free_image, free_audio FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone(); conn.close()
    if row: return {"username": row[0], "is_banned": bool(row[1]), "total_generated": row[2], "free_image": row[3], "free_audio": row[4]}
    return None

def db_add_user(user_id, username):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit(); conn.close()

def db_update_user(user_id, **kwargs):
    conn = get_conn(); c = conn.cursor()
    for key, val in kwargs.items():
        if key == "is_banned": val = 1 if val else 0
        c.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (val, user_id))
    conn.commit(); conn.close()

def db_get_all_users():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT user_id, username, is_banned, total_generated FROM users")
    rows = c.fetchall(); conn.close()
    return rows

def db_set_setting(key, value):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit(); conn.close()

# Функции для отложенных подарков
def db_add_pending_gift(username, f_img, f_aud):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT INTO pending_gifts (username, free_image, free_audio) VALUES (?, ?, ?) ON CONFLICT(username) DO UPDATE SET free_image = free_image + excluded.free_image, free_audio = free_audio + excluded.free_audio", (username.lower(), f_img, f_aud))
    conn.commit(); conn.close()

def db_claim_pending_gift(username):
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT free_image, free_audio FROM pending_gifts WHERE username = ?", (username.lower(),))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM pending_gifts WHERE username = ?", (username.lower(),))
        conn.commit(); conn.close()
        return row[0], row[1] # Возвращает картинки, музыку
    conn.close()
    return 0, 0

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🖼 Картинки"), types.KeyboardButton("🎵 Музыка"))
    markup.add(types.KeyboardButton("💳 Купить генерации (₽)")) 
    markup.add(types.KeyboardButton("📄 Документы"), types.KeyboardButton("📞 Поддержка"))
    markup.add(types.KeyboardButton("ℹ️ О боте"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("🛡 Админ-панель"))
    return markup

# ==========================================
# 3. ОБРАБОТЧИКИ БОТА
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    global promo_active
    uid = message.from_user.id
    uname = message.from_user.username or f"id{uid}"
    
    is_new = False
    if not db_get_user(uid):
        db_add_user(uid, uname)
        is_new = True

    # 1. Проверяем отложенные подарки для этого юзернейма
    pending_img, pending_aud = db_claim_pending_gift(uname)
    if pending_img > 0 or pending_aud > 0:
        u = db_get_user(uid)
        db_update_user(uid, free_image=u["free_image"] + pending_img, free_audio=u["free_audio"] + pending_aud)
        bot.send_message(uid, f"🎁 <b>Тебе начислен бонус!</b>\n+{pending_img} картинок, +{pending_aud} музыки.", parse_mode="HTML")

    # 2. Если акция включена и пользователь новый — начисляем бонус
    if is_new and promo_active:
        u = db_get_user(uid)
        # Чтобы не задваивать, если ему уже выдали отложенный подарок
        if pending_img == 0 and pending_aud == 0:
            db_update_user(uid, free_image=u["free_image"] + 3, free_audio=u["free_audio"] + 3)
            bot.send_message(uid, "🎁 <b>Бонус за регистрацию!</b>\nТебе начислено 3 бесплатные генерации картинок и 3 генерации музыки!", parse_mode="HTML")

    u = db_get_user(uid)
    if u["is_banned"]:
        return bot.send_message(uid, "⛔ Вы забанены в этом боте.")

    bot.send_message(
        uid,
        f"👋 Привет, @{uname}!\n\n"
        f"Я — <b>Нейро-Студия</b>. Могу нарисовать картинку или создать музыку.\n"
        f"Сгенерировано: {u['total_generated']}\n\n"
        f"🔑 <b>Для тестирования фильтров банком введите кодовое слово:</b> verplatega", 
        reply_markup=get_main_menu(uid),
        parse_mode="HTML"
    )

@bot.message_handler(commands=['verplatega'])
def check_verplatega(message):
    bot.send_message(message.chat.id, "✅ Тестовый режим Platega активен. Фильтры NSFW и запрещенного контента работают в штатном режиме.")

@bot.message_handler(func=lambda message: message.text == "ℹ️ О боте")
def about_bot(message):
    bot.send_message(message.chat.id, "Бот генерирует картинки и музыку через Polza.ai.")

@bot.message_handler(func=lambda message: message.text == "📄 Документы")
def show_docs(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📜 Пользовательское соглашение", url=TERMS_URL),
        types.InlineKeyboardButton("🔒 Политика конфиденциальности", url=PRIVACY_URL)
    )
    bot.send_message(message.chat.id, "📄 <b>Документы проекта:</b>", reply_markup=markup, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "📞 Поддержка")
def support(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Написать в поддержку", url="https://t.me/crptworking"))
    bot.send_message(message.chat.id, "Напишите нам:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "💳 Купить генерации (₽)")
def buy_rub_menu(message):
    text = (
        "💳 <b>Покупка генераций за рубли</b>\n\n"
        "• 10 генераций — <b>100 ₽</b>\n"
        "• 25 генераций — <b>200 ₽</b>\n"
        "• 50 генераций — <b>350 ₽</b>\n\n"
        "Оплата временно недоступна."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Оплатить 100 ₽", callback_data="pay_rub_stub"))
    markup.add(types.InlineKeyboardButton("💰 Оплатить 200 ₽", callback_data="pay_rub_stub"))
    markup.add(types.InlineKeyboardButton("💰 Оплатить 350 ₽", callback_data="pay_rub_stub"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "pay_rub_stub")
def pay_rub_stub(call):
    bot.answer_callback_query(call.id, "⏳ Оплата временно недоступна.", show_alert=True)

@bot.message_handler(func=lambda message: message.text in ["🖼 Картинки", "🎵 Музыка"])
def choose_category(message):
    uid = message.from_user.id
    u = db_get_user(uid)
    if u and u["is_banned"]: return

    category = "image" if message.text == "🖼 Картинки" else "audio"
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for model_id, m_type in MODEL_TYPES.items():
        if m_type == category:
            price = MODEL_PRICES_RUB.get(model_id, 10)
            btn_text = f"{MODEL_NAMES[model_id]} ({price}₽)"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"model_{model_id}"))
    
    bot.send_message(message.chat.id, "Выбери модель:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("model_"))
def ask_prompt(call):
    bot.answer_callback_query(call.id)
    uid = call.from_user.id
    model_id = call.data.replace("model_", "")
    
    if model_id not in MODEL_NAMES:
        return bot.send_message(uid, "❌ Модель не найдена.")

    price = MODEL_PRICES_RUB.get(model_id, 10)
    user_data[uid] = {"model": model_id, "price": price}
    
    msg = bot.send_message(uid, f"Выбрана: <b>{MODEL_NAMES[model_id]}</b> ({price}₽).\n\nНапиши запрос:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_prompt)

def process_prompt(message):
    uid = message.from_user.id
    prompt = message.text
    
    if prompt.lower() == "verplatega":
        return bot.send_message(uid, "✅ Тестовый режим Platega активен. Фильтры работают.")

    banned_words = ["порно", "секс", "голая", "насилие", "оружие", "наркотики", "детское", "убийство", "кровь"]
    if any(word in prompt.lower() for word in banned_words):
        return bot.send_message(uid, "❌ Запрос нарушает правила безопасности.")

    if len(prompt) < 3:
        return bot.send_message(uid, "❌ Опиши подробнее.")

    data = user_data.get(uid)
    if not data:
        return bot.send_message(uid, "❌ Сессия истекла.")

    data["prompt"] = prompt
    model_id = data["model"]
    price = data["price"]
    m_type = MODEL_TYPES[model_id]

    u = db_get_user(uid)
    if uid == ADMIN_ID:
        bot.send_message(uid, "👑 Режим админа: бесплатно!")
        generate_media(uid, prompt, model_id)
        return

    if m_type == "image" and u["free_image"] > 0:
        db_update_user(uid, free_image=u["free_image"] - 1)
        bot.send_message(uid, f"🎁 Бесплатная генерация! Осталось: {u['free_image'] - 1}")
        generate_media(uid, prompt, model_id)
        return

    if m_type == "audio" and u["free_audio"] > 0:
        db_update_user(uid, free_audio=u["free_audio"] - 1)
        bot.send_message(uid, f"🎁 Бесплатная генерация! Осталось: {u['free_audio'] - 1}")
        generate_media(uid, prompt, model_id)
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"💳 Оплатить {price} ₽", callback_data="pay_rub_stub_quick"))
    bot.send_message(uid, f"💳 Для генерации нужно оплатить <b>{price} ₽</b>.", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "pay_rub_stub_quick")
def pay_rub_stub_quick(call):
    bot.answer_callback_query(call.id, "⏳ Оплата временно недоступна.", show_alert=True)

# ==========================================
# 4. ГЕНЕРАЦИЯ
# ==========================================
def generate_media(uid, prompt, model_id):
    media_type = MODEL_TYPES[model_id]
    action = 'upload_photo' if media_type == 'image' else 'upload_voice'
    try: bot.send_chat_action(uid, action)
    except: pass
    
    try:
        headers = {"Authorization": f"Bearer {POLZA_API_KEY}", "Content-Type": "application/json"}
        if media_type == "image":
            payload = {"model": model_id, "input": {"prompt": prompt, "aspect_ratio": "1:1", "image_resolution": "1K"}, "async": False}
        else:
            payload = {"model": model_id, "input": {"prompt": prompt}, "async": False}
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=130)
        res_data = response.json()

        if response.status_code != 200:
            error_msg = res_data.get('error', {}).get('message', 'Неизвестная ошибка')
            bot.send_message(uid, f"❌ Ошибка API: {error_msg}")
            return

        media_id = res_data.get("id")
        if res_data.get("status") == "pending" and media_id:
            for _ in range(40):
                time.sleep(3)
                check_resp = requests.get(f"{API_URL}/{media_id}", headers=headers, timeout=10)
                check_data = check_resp.json()
                if check_data.get("status") == "completed":
                    res_data = check_data; break
                elif check_data.get("status") == "failed":
                    return bot.send_message(uid, "❌ Генерация не удалась.")
            else:
                return bot.send_message(uid, "⏳ Время ожидания истекло.")

        media_url = None
        if "data" in res_data and isinstance(res_data["data"], list) and len(res_data["data"]) > 0:
            media_url = res_data["data"][0].get("url")
        elif "url" in res_data:
            media_url = res_data["url"]
            
        if not media_url:
            return bot.send_message(uid, "❌ Ошибка: API не вернул ссылку.")

        file_resp = requests.get(media_url, timeout=60)
        file_ext = ".jpg" if media_type == "image" else ".mp3"
        temp_filename = f"temp_{uid}{file_ext}"
        
        with open(temp_filename, "wb") as f:
            f.write(file_resp.content)

        try:
            with open(temp_filename, "rb") as f:
                if media_type == "image":
                    bot.send_photo(uid, f, caption=f"🎨 {MODEL_NAMES[model_id]}\nЗапрос: {prompt}")
                else:
                    bot.send_audio(uid, f, caption=f"🎵 {MODEL_NAMES[model_id]}\nЗапрос: {prompt}")
        except: pass
        
        if os.path.exists(temp_filename): os.remove(temp_filename)
        
        u = db_get_user(uid)
        if u: db_update_user(uid, total_generated=u["total_generated"] + 1)
        if uid in user_data: del user_data[uid]

    except Exception as e:
        print(f"Ошибка в generate_media: {e}")

# ==========================================
# 5. АДМИН-ПАНЕЛЬ
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🛡 Админ-панель")
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 Забанить/Разбанить", callback_data="adm_ban"),
        types.InlineKeyboardButton("🎁 Выдать генерации", callback_data="adm_gift")
    )
    markup.add(types.InlineKeyboardButton("👥 Список юзеров", callback_data="adm_users"))
    
    status = "🟢 ВКЛ" if promo_active else "🔴 ВЫКЛ"
    markup.add(types.InlineKeyboardButton(f"🎁 Бонус 3 генерации (сейчас: {status})", callback_data="adm_promo_menu"))
    
    bot.send_message(message.chat.id, "🛡 <b>Админ-панель</b>", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_actions(call):
    global promo_active
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "❌ Нет доступа.")
    bot.answer_callback_query(call.id)
    act = call.data.split("_")[1]

    if act == "stats":
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users"); total_users = c.fetchone()[0]
        c.execute("SELECT SUM(total_generated) FROM users"); total_images = c.fetchone()[0] or 0
        conn.close()
        bot.send_message(call.message.chat.id, f"📊 <b>Статистика:</b>\n\n👥 Пользователей: {total_users}\n🎨/🎵 Сгенерировано: {total_images}", parse_mode="HTML")

    elif act == "broadcast":
        msg = bot.send_message(call.message.chat.id, "Введи текст для рассылки:")
        bot.register_next_step_handler(msg, admin_broadcast)
    elif act == "ban":
        msg = bot.send_message(call.message.chat.id, "Напиши <code>@username</code> или ID:")
        bot.register_next_step_handler(msg, admin_ban_user)
    elif act == "gift":
        msg = bot.send_message(call.message.chat.id, "Напиши <code>@username image 2</code>:")
        bot.register_next_step_handler(msg, admin_gift_generation)
    elif act == "users":
        users = db_get_all_users()
        if not users: return bot.send_message(call.message.chat.id, "Пользователей нет.")
        text = "👥 <b>Список:</b>\n\n"
        for u_id, uname, is_banned, total in users:
            status = "🚫" if is_banned else "✅"
            text += f"{status} @{uname} — ген: {total}\n"
            if len(text) > 3500:
                bot.send_message(call.message.chat.id, text, parse_mode="HTML"); text = ""
        if text: bot.send_message(call.message.chat.id, text, parse_mode="HTML")

    elif act == "promo_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🟢 Включить для новых", callback_data="adm_promo_on"))
        markup.add(types.InlineKeyboardButton("🎁 Выдать всем старым", callback_data="adm_promo_old"))
        markup.add(types.InlineKeyboardButton("🎁 Выдать всем (и старым, и новым)", callback_data="adm_promo_all"))
        markup.add(types.InlineKeyboardButton("🔴 Отключить акцию", callback_data="adm_promo_off"))
        bot.send_message(call.message.chat.id, "🎁 <b>Управление акцией:</b>", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_promo_"))
def admin_promo_actions(call):
    global promo_active
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "❌ Нет доступа.")
    bot.answer_callback_query(call.id)
    action = call.data.replace("adm_promo_", "")

    if action == "on":
        promo_active = True
        db_set_setting("promo_active", "1")
        bot.send_message(call.message.chat.id, "✅ Акция включена! Все новые пользователи при /start получат 3 картинки и 3 музыки.")
    elif action == "off":
        promo_active = False
        db_set_setting("promo_active", "0")
        bot.send_message(call.message.chat.id, "🛑 Акция отключена.")
    elif action == "old":
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()
        for row in users:
            uid = row[0]
            u = db_get_user(uid)
            if u:
                db_update_user(uid, free_image=u["free_image"] + 3, free_audio=u["free_audio"] + 3)
        bot.send_message(call.message.chat.id, f"✅ Выдано по 3+3 генерации всем старым ({len(users)} чел).")
    elif action == "all":
        promo_active = True
        db_set_setting("promo_active", "1")
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()
        for row in users:
            uid = row[0]
            u = db_get_user(uid)
            if u:
                db_update_user(uid, free_image=u["free_image"] + 3, free_audio=u["free_audio"] + 3)
        bot.send_message(call.message.chat.id, f"✅ Выдано по 3+3 всем ({len(users)} чел), а новым будет выдаваться автоматом.")

def admin_broadcast(message):
    conn = get_conn(); c = conn.cursor(); c.execute("SELECT user_id FROM users WHERE is_banned = 0"); users = c.fetchall(); conn.close()
    ok, fail = 0, 0
    for row in users:
        try: bot.send_message(row[0], message.text); ok += 1
        except: fail += 1
    bot.send_message(message.chat.id, f"✅ Рассылка: {ok} ок, {fail} ошибок.")

def admin_ban_user(message):
    identifier = message.text.strip().replace("@", "")
    conn = get_conn(); c = conn.cursor()
    if identifier.isdigit(): c.execute("SELECT user_id, username, is_banned FROM users WHERE user_id = ?", (int(identifier),))
    else: c.execute("SELECT user_id, username, is_banned FROM users WHERE LOWER(username) = ?", (identifier.lower(),))
    row = c.fetchone(); conn.close()
    if not row: return bot.send_message(message.chat.id, "❌ Не найден.")
    uid, uname, is_banned = row
    new_status = not bool(is_banned)
    db_update_user(uid, is_banned=new_status)
    bot.send_message(message.chat.id, f"✅ @{uname} {'забанен' if new_status else 'разбанен'}.")

def admin_gift_generation(message):
    try:
        parts = message.text.split()
        identifier = parts[0].replace("@", ""); m_type = parts[1].lower(); amount = int(parts[2])
        if m_type not in ["image", "audio"]: return bot.send_message(message.chat.id, "❌ Тип: image/audio.")
        
        conn = get_conn(); c = conn.cursor()
        if identifier.isdigit(): c.execute("SELECT user_id, username, free_image, free_audio FROM users WHERE user_id = ?", (int(identifier),))
        else: c.execute("SELECT user_id, username, free_image, free_audio FROM users WHERE LOWER(username) = ?", (identifier.lower(),))
        row = c.fetchone(); conn.close()
        
        # Если пользователь найден в базе
        if row:
            uid, uname, f_img, f_aud = row
            if m_type == "image": db_update_user(uid, free_image=f_img + amount)
            else: db_update_user(uid, free_audio=f_aud + amount)
            bot.send_message(message.chat.id, f"✅ @{uname} выдано {amount} {m_type}.")
            try: bot.send_message(uid, f"🎁 Тебе выдано {amount} бесплатных генераций!")
            except: pass
        else:
            # Если пользователь НЕ найден (не нажимал /start) — делаем отложенный подарок
            if m_type == "image": db_add_pending_gift(identifier, amount, 0)
            else: db_add_pending_gift(identifier, 0, amount)
            bot.send_message(message.chat.id, f"✅ Пользователь @{identifier} еще не заходил. Бонус ({amount} {m_type}) будет выдан автоматически, как только он нажмет /start.")
            
    except: bot.send_message(message.chat.id, "❌ Ошибка. Пример: <code>@user image 2</code>", parse_mode="HTML")

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    print("🚀 Нейро-Студия запущена.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
