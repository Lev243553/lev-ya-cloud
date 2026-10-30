import telebot
from telebot import types
import requests
import time
import os

# Твой токен бота (лучше вынести в переменные Bothost)
TOKEN = "8959456335:AAFmQZmvsWuma4U0TZhIpBQJ8Kd2VOHwRN8" 
# Твой ключ Polza (лучше вынести в переменные Bothost)
POLZA_API_KEY = "pza_qGQO8ZXtNks1OxNxKOGjd-Y01K9i-E0g"

# ID модели Polza
MODEL_NAME = "openai/gpt-5.4-image-2"
API_URL = "https://polza.ai/api/v1/media"

bot = telebot.TeleBot(TOKEN, threaded=True)
PRICE_STARS = 10

# Временное хранилище для промптов (в реальном проекте используй SQLite)
# Сюда сохраняем текст запроса до оплаты, чтобы знать, что рисовать
user_prompts = {}

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        f"👋 Привет! Я — **Нейро-Художник**.\n\n"
        f"Я нарисую всё, что ты захочешь, с помощью модели GPT-5.4 Image 2.\n"
        f"💰 Стоимость одной картинки: **{PRICE_STARS} Stars**.\n\n"
        f"Просто напиши, что мне нарисовать 👇",
        parse_mode="Markdown"
    )

# Ловим описание картинки
@bot.message_handler(content_types=['text'])
def ask_for_payment(message):
    prompt = message.text
    if len(prompt) < 3:
        return bot.send_message(message.chat.id, "❌ Опиши картинку подробнее.")

    # Сохраняем промпт по ID пользователя
    user_prompts[message.from_user.id] = prompt

    # Выставляем счёт на 10 звёзд
    markup = types.InlineKeyboardMarkup()
    pay_btn = types.InlineKeyboardButton(f"⭐ Оплатить {PRICE_STARS} Stars", pay=True)
    markup.add(pay_btn)

    bot.send_invoice(
        chat_id=message.chat.id,
        title="Генерация картинки",
        description=f"Картинка по запросу: {prompt[:50]}...",
        invoice_payload="gen_payment", 
        provider_token="", 
        currency="XTR", # Код Telegram Stars
        prices=[types.LabeledPrice(label="Картинка", amount=PRICE_STARS)],
        reply_markup=markup
    )

# Подтверждаем готовность принять оплату
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Ловим успешную оплату
@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    bot.send_message(message.chat.id, "✅ Оплата получена! Начинаю рисовать...")
    
    # Достаем сохраненный промпт
    prompt = user_prompts.get(message.from_user.id, "красивый пейзаж")
    
    bot.send_chat_action(message.chat.id, 'upload_photo')
    
    try:
        # 1. Отправляем запрос на генерацию в Polza
        headers = {
            "Authorization": f"Bearer {POLZA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": MODEL_NAME,
            "input": {
                "prompt": prompt,
                "aspect_ratio": "1:1", # Квадратная картинка
                "image_resolution": "1K" # Разрешение
            },
            "async": False # Ждем результат синхронно (до 120 сек)
        }
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=130)
        data = response.json()

        # 2. Проверяем ответ
        if response.status_code != 200:
            error_msg = data.get('error', {}).get('message', str(data))
            return bot.send_message(message.chat.id, f"❌ Ошибка API: {error_msg}")

        # 3. Извлекаем URL картинки
        # Polza возвращает объект со статусом pending, но для синхронного запроса
        # результат должен быть сразу, либо нужно опрашивать статус.
        # Если пришел статус pending, нужно подождать.
        media_id = data.get("id")
        status = data.get("status")
        
        # Если статус pending, опрашиваем результат (максимум 120 секунд)
        if status == "pending" and media_id:
            for _ in range(40): # 40 попыток * 3 сек = 120 сек
                time.sleep(3)
                check_resp = requests.get(f"{API_URL}/{media_id}", headers=headers, timeout=10)
                check_data = check_resp.json()
                if check_data.get("status") == "completed":
                    data = check_data
                    break
                elif check_data.get("status") == "failed":
                    return bot.send_message(message.chat.id, "❌ Генерация не удалась. Попробуй другой запрос.")
            else:
                return bot.send_message(message.chat.id, "⏳ Генерация заняла слишком много времени. Попробуй позже.")

        # 4. Отправляем картинку
        # В ответе Polza URL обычно лежит в data -> data -> url
        # Структура может отличаться, поэтому ищем URL рекурсивно
        image_url = None
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            image_url = data["data"][0].get("url")
        elif "url" in data:
            image_url = data["url"]
            
        if not image_url:
            return bot.send_message(message.chat.id, f"❌ Не удалось найти URL картинки в ответе. Ответ: {data}")

        bot.send_photo(
            message.chat.id, 
            image_url, 
            caption=f"🎨 Твой запрос: {prompt}"
        )
        
        # Очищаем сохраненный промпт
        if message.from_user.id in user_prompts:
            del user_prompts[message.from_user.id]

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {e}")

if __name__ == "__main__":
    print("🚀 Фотобот запущен.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
