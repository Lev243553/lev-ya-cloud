import telebot
from telebot import types
import requests
import time
import os
import sqlite3

# Токен бота
TOKEN = "8959456335:AAFmQZmvsWuma4U0TZhIpBQJ8Kd2VOHwRN8" 
# Ключ Polza
POLZA_API_KEY = "pza_qGQO8ZXtNks1OxNxKOGjd-Y01K9i-E0g"

API_URL = "https://polza.ai/api/v1/media"
CHANNEL_USERNAME = "@PlameChat"
ADMIN_ID = 7031603236 # Твой ID

bot = telebot.TeleBot(TOKEN, threaded=True)
DB_PATH = "photo_bot.db"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        is_banned INTEGER DEFAULT 0,
        total_generated INTEGER DEFAULT 0
    )''')
    # Таблица для хранения цен (чтобы админ мог менять их на лету)
    c.execute('''CREATE TABLE IF NOT EXISTS prices (
        model_id TEXT PRIMARY KEY,
        price INTEGER
    )''')
    conn.commit()
    conn.close()

    # Заполняем начальные цены, если их нет
    conn = get_conn()
    c = conn.cursor()
    default_models = {
        "openai/gpt-image-1.5": 20,
        "openai/gpt-5-image": 25,
        "google/gemini-2.5-flash-image": 15,
        "google/gemini-3.1-flash-lite-image": 10,
        "google/gemini-nano-banana-2.1": 10,
        "black-forest-labs/flux.2-flex": 20,
        "bytedance/seedream-4": 15,
        "bytedance/seedream-5-lite": 10,
        "qwen/image": 10,
        "tongyi-mai/z-image": 10,
        "yandex/yandex-art": 10,
    }
    for model_id, price in default_models.items():
        c.execute("INSERT OR IGNORE INTO prices (model_id, price) VALUES (?, ?)", (model_id, price))
    conn.commit()
    conn.close()

init_db()

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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

# --- ДАННЫЕ МОДЕЛЕЙ (НАЗВАНИЯ) ---
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
}

user_data = {}

# --- ПРОВЕРКА ПОДПИСКИ ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return True 

def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🎨 Нарисовать картинку"))
    markup.add(types.KeyboardButton("ℹ️ О боте"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("🛡 Админ-панель"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    uname = message.from_user.username or f"id{uid}"
    
    # Регистрируем пользователя
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
        f"Я — **Нейро-Художник**. Нажми кнопку ниже, чтобы начать.\n\n"
        f"Сгенерировано картинок: {u['total_generated']}",
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
    bot.send_message(message.chat.id, "Бот генерирует картинки через Polza.ai. Выбери модель и напиши запрос.")

# --- ВЫБОР МОДЕЛИ ---
@bot.message_handler(func=lambda message: message.text == "🎨 Нарисовать картинку")
def choose_model(message):
    uid = message.from_user.id
    u = db_get_user(uid)
    if u and u["is_banned"]: return
    if not check_subscription(uid): return start(message)

    prices = db_get_prices()
    markup = types.InlineKeyboardMarkup(row_width=2)
    for model_id in MODEL_NAMES:
        price = prices.get(model_id, 10)
        btn_text = f"{MODEL_NAMES[model_id]} ({price}⭐)"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"model_{model_id}"))
    
    bot.send_message(message.chat.id, "Выбери нейросеть для генерации:", reply_markup=markup)

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
    
    msg = bot.send_message(uid, f"Выбрана модель: **{MODEL_NAMES[model_id]}** ({price}⭐).\n\nНапиши, что нарисовать:")
    bot.register_next_step_handler(msg, process_prompt)

def process_prompt(message):
    uid = message.from_user.id
    prompt = message.text
    
    if len(prompt) < 3:
        return bot.send_message(uid, "❌ Опиши картинку подробнее.")

    data = user_data.get(uid)
    if not data:
        return bot.send_message(uid, "❌ Сессия истекла. Начни заново.")

    data["prompt"] = prompt
    model_id = data["model"]
    price = data["price"]

    # --- БЕСПЛАТНО ДЛЯ АДМИНА ---
    if uid == ADMIN_ID:
        bot.send_message(uid, "👑 Режим админа: генерация бесплатна!")
        bot.send_chat_action(uid, 'upload_photo')
        generate_image(uid, prompt, model_id)
        return

    # --- ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ ---
    markup = types.InlineKeyboardMarkup()
    pay_btn = types.InlineKeyboardButton(f"⭐ Оплатить {price} Stars", pay=True)
    markup.add(pay_btn)

    bot.send_invoice(
        chat_id=uid,
        title=f"Генерация: {MODEL_NAMES[model_id]}",
        description=f"Картинка: {prompt[:50]}...",
        invoice_payload="gen_payment", 
        provider_token="", 
        currency="XTR",
        prices=[types.LabeledPrice(label="Картинка", amount=price)],
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
    
    bot.send_message(uid, f"✅ Оплата получена! Рисую через **{MODEL_NAMES[model_id]}**...", parse_mode="Markdown")
    generate_image(uid, prompt, model_id)

# --- ФУНКЦИЯ ГЕНЕРАЦИИ ---
def generate_image(uid, prompt, model_id):
    bot.send_chat_action(uid, 'upload_photo')
    
    try:
        headers = {
            "Authorization": f"Bearer {POLZA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_id,
            "input": {
                "prompt": prompt,
                "aspect_ratio": "1:1",
                "image_resolution": "1K"
            },
            "async": False 
        }
        
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

        image_url = None
        if "data" in res_data and isinstance(res_data["data"], list) and len(res_data["data"]) > 0:
            image_url = res_data["data"][0].get("url")
        elif "url" in res_data:
            image_url = res_data["url"]
            
        if not image_url:
            return bot.send_message(uid, f"❌ Ошибка: URL картинки не найден.")

        bot.send_photo(uid, image_url, caption=f"🎨 {MODEL_NAMES[model_id]}\nЗапрос: {prompt}")
        
        # Обновляем статистику
        u = db_get_user(uid)
        if u:
            db_update_user(uid, total_generated=u["total_generated"] + 1)
            
        if uid in user_data:
            del user_data[uid]

    except Exception as e:
        bot.send_message(uid, f"❌ Произошла ошибка: {e}")

# --- АДМИН-ПАНЕЛЬ ---
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
        bot.send_message(call.message.chat.id, f"📊 <b>Статистика:</b>\n\n👥 Пользователей: {total_users}\n🎨 Сгенерировано картинок: {total_images}", parse_mode="HTML")

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

if __name__ == "__main__":
    print("🚀 Фотобот с админкой запущен.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
