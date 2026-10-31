import telebot
from telebot import types
import requests
import time
import os
import sqlite3

# --- НАСТРОЙКИ ---
TOKEN = "8959456335:AAFmQZmvsWuma4U0TZhIpBQJ8Kd2VOHwRN8" 
POLZA_API_KEY = "pza_qGQO8ZXtNks1OxNxKOGjd-Y01K9i-E0g"
API_URL = "https://polza.ai/api/v1/media"
CHANNEL_USERNAME = "@PlameChat"
ADMIN_ID = 7031603236
DB_PATH = "media_bot.db"

bot = telebot.TeleBot(TOKEN, threaded=True)

MODEL_NAMES = {
    "openai/gpt-image-1.5": "GPT Image 1.5",
    "openai/gpt-5-image": "GPT-5 Image",
    "google/gemini-2.5-flash-image": "Gemini 2.5 Flash",
    "google/gemini-3.1-flash-lite-image": "Gemini 3.1 Lite",
    "google/gemini-nano-banana-2.1": "Nano Banana 2.1",
    "black-forest-labs/flux.2-flex": "Flux 2 Flex",
    "bytedance/seedream-4": "Seedream 4",
    "bytedance/seedream-5-lite": "Seedream 5 Lite",
    "qwen/image": "Qwen Image",
    "tongyi-mai/z-image": "Tongyi Z-Image",
    "yandex/yandex-art": "Yandex Art",
    "google/lyria-3-pro-preview": "Lyria 3 Pro",
    "suno/sounds": "Suno Sounds",
    "google/lyria-3-clip-preview": "Lyria 3 Clip"
}

MODEL_TYPES = {
    "openai/gpt-image-1.5": "image", "openai/gpt-5-image": "image", "google/gemini-2.5-flash-image": "image",
    "google/gemini-3.1-flash-lite-image": "image", "google/gemini-nano-banana-2.1": "image", "black-forest-labs/flux.2-flex": "image",
    "bytedance/seedream-4": "image", "bytedance/seedream-5-lite": "image", "qwen/image": "image", "tongyi-mai/z-image": "image",
    "yandex/yandex-art": "image",
    "google/lyria-3-pro-preview": "audio", "suno/sounds": "audio", "google/lyria-3-clip-preview": "audio"
}

user_data = {}

# ==========================================
# 1. БАЗА ДАННЫХ
# ==========================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, is_banned INTEGER DEFAULT 0, total_generated INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS prices (
        model_id TEXT PRIMARY KEY, price INTEGER
    )''')
    
    default_models = {
        "openai/gpt-image-1.5": 20, "openai/gpt-5-image": 25, "google/gemini-2.5-flash-image": 15,
        "google/gemini-3.1-flash-lite-image": 10, "google/gemini-nano-banana-2.1": 10, "black-forest-labs/flux.2-flex": 20,
        "bytedance/seedream-4": 15, "bytedance/seedream-5-lite": 10, "qwen/image": 10, "tongyi-mai/z-image": 10,
        "yandex/yandex-art": 10,
        "google/lyria-3-pro-preview": 25, "suno/sounds": 10, "google/lyria-3-clip-preview": 15
    }
    for model_id, price in default_models.items():
        c.execute("INSERT OR IGNORE INTO prices (model_id, price) VALUES (?, ?)", (model_id, price))
        
    conn.commit()
    conn.close()

init_db()

def db_get_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username, is_banned, total_generated FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "is_banned": bool(row[1]), "total_generated": row[2]}
    return None

def db_add_user(user_id, username):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def db_update_user(user_id, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    for key, val in kwargs.items():
        if key == "is_banned": val = 1 if val else 0
        c.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (val, user_id))
    conn.commit()
    conn.close()

def db_get_prices():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT model_id, price FROM prices")
    rows = c.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def db_update_price(model_id, price):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE prices SET price = ? WHERE model_id = ?", (price, model_id))
    conn.commit()
    conn.close()

def db_get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, username, is_banned, total_generated FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return True 

def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🖼 Картинки"), types.KeyboardButton("🎵 Музыка"))
    markup.add(types.KeyboardButton("ℹ️ О боте"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("🛡 Админ-панель"))
    return markup

# ==========================================
# 3. ОБРАБОТЧИКИ БОТА
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    uname = message.from_user.username or f"id{uid}"
    
    if not db_get_user(uid):
        db_add_user(uid, uname)

    u = db_get_user(uid)
    if u["is_banned"]:
        return bot.send_message(uid, "⛔ Вы забанены в этом боте.")

    if not check_subscription(uid):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📺 Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"),
            types.InlineKeyboardButton("✅ Я подписался (Проверить)", callback_data="check_sub")
        )
        return bot.send_message(uid, "Для использования бота подпишись на канал.", reply_markup=markup)

    bot.send_message(
        uid,
        f"👋 Привет, @{uname}!\n\n"
        f"Я — **Нейро-Студия**. Могу нарисовать картинку или создать музыку.\n\n"
        f"Сгенерировано: {u['total_generated']}",
        reply_markup=get_main_menu(uid),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    bot.answer_callback_query(call.id)
    if check_subscription(call.from_user.id):
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        start(call.message)
    else:
        bot.send_message(call.message.chat.id, "❌ Вы всё ещё не подписаны.")

@bot.message_handler(func=lambda message: message.text == "ℹ️ О боте")
def about_bot(message):
    bot.send_message(message.chat.id, "Бот генерирует картинки и музыку через Polza.ai. Выбери категорию и напиши запрос.")

@bot.message_handler(func=lambda message: message.text in ["🖼 Картинки", "🎵 Музыка"])
def choose_category(message):
    uid = message.from_user.id
    u = db_get_user(uid)
    if u and u["is_banned"]: return
    if not check_subscription(uid): return start(message)

    category = "image" if message.text == "🖼 Картинки" else "audio"
    prices = db_get_prices()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for model_id, m_type in MODEL_TYPES.items():
        if m_type == category:
            price = prices.get(model_id, 10)
            btn_text = f"{MODEL_NAMES[model_id]} ({price}⭐)"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"model_{model_id}"))
    
    title = "Выбери модель для картинок:" if category == "image" else "Выбери модель для музыки:"
    bot.send_message(message.chat.id, title, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("model_"))
def ask_prompt(call):
    bot.answer_callback_query(call.id)
    uid = call.from_user.id
    model_id = call.data.replace("model_", "")
    
    if model_id not in MODEL_NAMES:
        return bot.send_message(uid, "❌ Модель не найдена.")

    prices = db_get_prices()
    price = prices.get(model_id, 10)
    
    user_data[uid] = {"model": model_id, "price": price}
    
    action = "нарисовать" if MODEL_TYPES[model_id] == "image" else "создать"
    msg = bot.send_message(uid, f"Выбрана модель: **{MODEL_NAMES[model_id]}** ({price}⭐).\n\nНапиши, что {action}:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_prompt)

def process_prompt(message):
    uid = message.from_user.id
    prompt = message.text
    
    if len(prompt) < 3:
        return bot.send_message(uid, "❌ Опиши подробнее.")

    data = user_data.get(uid)
    if not data:
        return bot.send_message(uid, "❌ Сессия истекла. Начни заново.")

    data["prompt"] = prompt
    model_id = data["model"]
    price = data["price"]

    if uid == ADMIN_ID:
        bot.send_message(uid, "👑 Режим админа: бесплатно!")
        generate_media(uid, prompt, model_id)
        return

    markup = types.InlineKeyboardMarkup()
    pay_btn = types.InlineKeyboardButton(f"⭐ Оплатить {price} Stars", pay=True)
    markup.add(pay_btn)

    media_type = "картинку" if MODEL_TYPES[model_id] == "image" else "музыку"
    bot.send_invoice(
        chat_id=uid,
        title=f"Генерация: {MODEL_NAMES[model_id]}",
        description=f"Создать {media_type}: {prompt[:50]}...",
        invoice_payload="gen_payment", 
        provider_token="", 
        currency="XTR",
        prices=[types.LabeledPrice(label="Генерация", amount=price)],
        reply_markup=markup
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = message.from_user.id
    data = user_data.get(uid)
    
    if not data:
        return bot.send_message(uid, "❌ Ошибка: данные заказа потеряны.")

    prompt = data["prompt"]
    model_id = data["model"]
    
    bot.send_message(uid, f"✅ Оплата получена! Создаю через **{MODEL_NAMES[model_id]}**...", parse_mode="Markdown")
    generate_media(uid, prompt, model_id)

# ==========================================
# 4. ГЕНЕРАЦИЯ (С ЗАЩИТОЙ ОТ ОШИБОК)
# ==========================================
def generate_media(uid, prompt, model_id):
    media_type = MODEL_TYPES[model_id]
    action = 'upload_photo' if media_type == 'image' else 'upload_voice'
    
    try:
        bot.send_chat_action(uid, action)
    except Exception:
        pass
        
    try:
        headers = {
            "Authorization": f"Bearer {POLZA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        if media_type == "image":
            payload = {"model": model_id, "input": {"prompt": prompt, "aspect_ratio": "1:1", "image_resolution": "1K"}, "async": False}
        else:
            payload = {"model": model_id, "input": {"prompt": prompt}, "async": False}
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=130)
        res_data = response.json()

        if response.status_code != 200:
            error_msg = res_data.get('error', {}).get('message', str(res_data))
            return bot.send_message(uid, f"❌ Ошибка API: {error_msg}")

        media_id = res_data.get("id")
        status = res_data.get("status")
        
        if status == "pending" and media_id:
            for _ in range(40):
                time.sleep(3)
                check_resp = requests.get(f"{API_URL}/{media_id}", headers=headers, timeout=10)
                check_data = check_resp.json()
                if check_data.get("status") == "completed":
                    res_data = check_data
                    break
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
            return bot.send_message(uid, f"❌ Ошибка: API вернул некорректный URL.")

        bot.send_message(uid, "⏳ Скачиваю готовый файл...")
        file_resp = requests.get(media_url, timeout=60)
        
        if file_resp.status_code != 200:
            return bot.send_message(uid, "❌ Не удалось скачать файл.")

        file_ext = ".jpg" if media_type == "image" else ".mp3"
        temp_filename = f"temp_{uid}{file_ext}"
        
        with open(temp_filename, "wb") as f:
            f.write(file_resp.content)

        # --- ЗАЩИТА ОТ 403 ОШИБКИ (ПОПЫТКА НАПИСАТЬ БОТУ) ---
        try:
            with open(temp_filename, "rb") as f:
                if media_type == "image":
                    bot.send_photo(uid, f, caption=f"🎨 {MODEL_NAMES[model_id]}\nЗапрос: {prompt}")
                else:
                    bot.send_audio(uid, f, caption=f"🎵 {MODEL_NAMES[model_id]}\nЗапрос: {prompt}")
        except Exception as send_error:
            print(f"Ошибка отправки пользователю {uid}: {send_error}")
            # Если это админ делал подарок, сообщаем ему об ошибке
            if uid != ADMIN_ID: 
                bot.send_message(ADMIN_ID, f"⚠️ Не удалось отправить файл пользователю {uid}: {send_error}")
        
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        
        u = db_get_user(uid)
        if u:
            db_update_user(uid, total_generated=u["total_generated"] + 1)
            
        if uid in user_data:
            del user_data[uid]

    except Exception as e:
        print(f"Критическая ошибка: {e}")

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
        types.InlineKeyboardButton("💰 Изменить цены", callback_data="adm_prices"),
        types.InlineKeyboardButton("🚫 Забанить/Разбанить", callback_data="adm_ban")
    )
    markup.add(
        types.InlineKeyboardButton("🎁 Выдать генерацию", callback_data="adm_gift"),
        types.InlineKeyboardButton("👥 Список юзеров", callback_data="adm_users")
    )
    bot.send_message(message.chat.id, "🛡 <b>Админ-панель</b>", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_actions(call):
    if call.from_user.id != ADMIN_ID: return bot.answer_callback_query(call.id, "❌ Нет доступа.")
    bot.answer_callback_query(call.id)
    act = call.data.split("_")[1]

    if act == "stats":
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT SUM(total_generated) FROM users")
        total_images = c.fetchone()[0] or 0
        conn.close()
        bot.send_message(call.message.chat.id, f"📊 <b>Статистика:</b>\n\n👥 Пользователей: {total_users}\n🎨/🎵 Сгенерировано: {total_images}", parse_mode="HTML")

    elif act == "broadcast":
        msg = bot.send_message(call.message.chat.id, "Введи текст для рассылки всем пользователям:")
        bot.register_next_step_handler(msg, admin_broadcast)

    elif act == "prices":
        prices = db_get_prices()
        text = "💰 <b>Текущие цены (Stars):</b>\n\n"
        for m_id, p in prices.items():
            text += f"• {MODEL_NAMES.get(m_id, m_id)}: {p}⭐\n"
        text += "\nНапиши название модели (или её часть) и новую цену через пробел.\nПример: <code>flux 30</code>"
        msg = bot.send_message(call.message.chat.id, text, parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_change_price)

    elif act == "ban":
        msg = bot.send_message(call.message.chat.id, "Напиши <code>@username</code> или ID пользователя, чтобы забанить/разбанить:")
        bot.register_next_step_handler(msg, admin_ban_user)

    elif act == "gift":
        msg = bot.send_message(call.message.chat.id, "Напиши <code>@username</code> (или ID) и тип: <code>image</code> или <code>audio</code>.\nПример: <code>@user image</code>")
        bot.register_next_step_handler(msg, admin_gift_generation)

    elif act == "users":
        users = db_get_all_users()
        if not users:
            return bot.send_message(call.message.chat.id, "Пользователей пока нет.")
        
        text = "👥 <b>Список пользователей:</b>\n\n"
        for u_id, uname, is_banned, total in users:
            status = "🚫" if is_banned else "✅"
            text += f"{status} @{uname} (ID: <code>{u_id}</code>) — сгенерировано: {total}\n"
            
            if len(text) > 3500:
                bot.send_message(call.message.chat.id, text, parse_mode="HTML")
                text = ""
        if text:
            bot.send_message(call.message.chat.id, text, parse_mode="HTML")

def admin_broadcast(message):
    text = message.text
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = c.fetchall()
    conn.close()
    
    ok, fail = 0, 0
    for row in users:
        try:
            bot.send_message(row[0], text)
            ok += 1
        except:
            fail += 1
    bot.send_message(message.chat.id, f"✅ Рассылка завершена.\nУспешно: {ok}\nОшибок: {fail}")

def admin_change_price(message):
    try:
        parts = message.text.split()
        query = parts[0].lower()
        new_price = int(parts[1])
        
        found_model = None
        for model_id in MODEL_NAMES:
            if query in model_id.lower() or query in MODEL_NAMES[model_id].lower():
                found_model = model_id
                break
        
        if not found_model:
            return bot.send_message(message.chat.id, "❌ Модель не найдена.")
            
        db_update_price(found_model, new_price)
        bot.send_message(message.chat.id, f"✅ Цена для {MODEL_NAMES[found_model]} изменена на {new_price}⭐.")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка. Пример: <code>flux 30</code>", parse_mode="HTML")

def admin_ban_user(message):
    identifier = message.text.strip().replace("@", "")
    conn = get_conn()
    c = conn.cursor()
    
    if identifier.isdigit():
        c.execute("SELECT user_id, username, is_banned FROM users WHERE user_id = ?", (int(identifier),))
    else:
        c.execute("SELECT user_id, username, is_banned FROM users WHERE LOWER(username) = ?", (identifier.lower(),))
        
    row = c.fetchone()
    conn.close()
    
    if not row:
        return bot.send_message(message.chat.id, "❌ Пользователь не найден в базе.")
        
    uid, uname, is_banned = row
    new_status = not bool(is_banned)
    
    db_update_user(uid, is_banned=new_status)
    status_text = "забанен" if new_status else "разбанен"
    bot.send_message(message.chat.id, f"✅ Пользователь @{uname} {status_text}.")

def admin_gift_generation(message):
    try:
        parts = message.text.split()
        identifier = parts[0].replace("@", "")
        m_type = parts[1].lower()
        
        if m_type not in ["image", "audio"]:
            return bot.send_message(message.chat.id, "❌ Тип должен быть 'image' или 'audio'.")
        
        conn = get_conn()
        c = conn.cursor()
        if identifier.isdigit():
            c.execute("SELECT user_id, username FROM users WHERE user_id = ?", (int(identifier),))
        else:
            c.execute("SELECT user_id, username FROM users WHERE LOWER(username) = ?", (identifier.lower(),))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return bot.send_message(message.chat.id, "❌ Пользователь не найден.")
            
        uid, uname = row
        
        bot.send_message(message.chat.id, f"Напиши промпт для генерации {m_type} для @{uname}:")
        bot.register_next_step_handler(message, process_gift_prompt, uid, m_type)
        
    except:
        bot.send_message(message.chat.id, "❌ Ошибка. Пример: <code>@user image</code>", parse_mode="HTML")

def process_gift_prompt(message, target_uid, m_type):
    prompt = message.text
    model_id = "openai/gpt-image-1.5" if m_type == "image" else "suno/sounds"
    
    bot.send_message(message.chat.id, f"🎁 Генерирую пробный {m_type} для пользователя...")
    generate_media(target_uid, prompt, model_id)
    bot.send_message(message.chat.id, "✅ Команда на генерацию отправлена!")

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    print("🚀 Нейро-Студия запущена.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
