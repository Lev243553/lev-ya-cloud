import telebot
from telebot import types
import os
from dotenv import load_dotenv
import requests
import base64

load_dotenv()

# ВСТАВЬ СВОЙ ТОКЕН СЮДА
TOKEN = "8959456335:AAFmQZmvsWuma4U0TZhIpBQJ8Kd2VOHwRN8"
API_KEY = "sk_66e27f139221a866f91c53377ab0c1ce8c16f6dcabb3b654"
API_URL = "https://api.provod.ai/v1/chat/completions"
MODEL_NAME = "minimax-m3.1-flash" 

bot = telebot.TeleBot(TOKEN, threaded=True)

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📝 Решить задачу"))
    markup.add(types.KeyboardButton("📖 Написать конспект"))
    markup.add(types.KeyboardButton("📊 Сделать презентацию"))
    markup.add(types.KeyboardButton("❓ Задать любой вопрос"))
    markup.add(types.KeyboardButton("ℹ️ О боте"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 Привет! Я твой Мини-ГДЗ.\n\n"
        "Я умею решать задачи, писать конспекты, собирать структуру презентаций. "
        "А еще я могу читать задания с фото!\n\n"
        "Выбери действие в меню или просто отправь мне фото с домашкой 👇",
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "ℹ️ О боте")
def about(message):
    bot.send_message(message.chat.id, "Я работаю на базе нейросети. Помогаю с учёбой.")

@bot.message_handler(func=lambda message: message.text in [
    "📝 Решить задачу", "📖 Написать конспект", "📊 Сделать презентацию", "❓ Задать любой вопрос"
])
def choose_action(message):
    action = message.text
    prompts = {
        "📝 Решить задачу": "Ты — учитель. Реши эту задачу по шагам, объясняя каждое действие. Задача: ",
        "📖 Написать конспект": "Ты — студент. Напиши краткий и понятный конспект по этой теме (выдели главное, используй списки). Тема: ",
        "📊 Сделать презентацию": "Ты — дизайнер презентаций. Составь структуру презентации из 5-7 слайдов на эту тему. Для каждого слайда напиши заголовок и 3 тезиса. Тема: ",
        "❓ Задать любой вопрос": "Ответь на этот вопрос кратко и понятно: "
    }
    prompt_prefix = prompts.get(action, "")
    msg = bot.send_message(message.chat.id, f"Отлично! Напиши тему или сам вопрос для «{action}»:")
    bot.register_next_step_handler(msg, generate_text_response, prompt_prefix)

# --- ОБРАБОТКА ТЕКСТА ---
def generate_text_response(message, prompt_prefix):
    bot.send_chat_action(message.chat.id, 'typing')
    full_prompt = f"{prompt_prefix}{message.text}"
    
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": full_prompt}],
        "max_tokens": 1500
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if 'choices' in data:
            answer = data['choices'][0]['message']['content']
        else:
            answer = f"Ошибка API: {data}"

        # Отправляем БЕЗ Markdown, чтобы не было ошибок парсинга
        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                bot.send_message(message.chat.id, answer[i:i+4000])
        else:
            bot.send_message(message.chat.id, answer)
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# --- ОБРАБОТКА ФОТО (ДОМАШКА) ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.send_message(message.chat.id, "⏳ Читаю задание с фото, подожди...")
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Скачиваем фото
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Переводим в base64
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')
        
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "user", "content": [
                    {"type": "text", "text": "Прочитай задание на фото и реши его по шагам, объясняя каждое действие."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            "max_tokens": 1500
        }
        
        response = requests.post(API_URL, headers=headers, json=payload, timeout=40)
        data = response.json()
        
        if 'choices' in data:
            answer = data['choices'][0]['message']['content']
        else:
            answer = f"Ошибка API: {data}"

        # Отправляем БЕЗ Markdown
        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                bot.send_message(message.chat.id, answer[i:i+4000])
        else:
            bot.send_message(message.chat.id, answer)
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при обработке фото: {e}")

if __name__ == "__main__":
    print("🚀 Мини-ГДЗ запущен.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
