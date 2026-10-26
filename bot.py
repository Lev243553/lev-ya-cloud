import telebot
from telebot import types
import os
from dotenv import load_dotenv
import requests

load_dotenv()

TOKEN = os.getenv("CONTENT_BOT_TOKEN")
API_KEY = os.getenv("KOSAREVA_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7031603236"))

# Базовый URL твоего API
API_URL = "https://api.kosareva.cloud/v1/chat/completions"
# Модель (если не работает, попробуй gpt-4o-mini)
MODEL_NAME = "gpt-3.5-turbo" 

bot = telebot.TeleBot(TOKEN, threaded=True)
PRICE_STARS = 20 

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("✍️ Написать пост"), types.KeyboardButton("📝 Сделать описание"))
    markup.add(types.KeyboardButton("🎓 Написать сочинение"), types.KeyboardButton("📖 Написать историю"))
    markup.add(types.KeyboardButton("ℹ️ О боте"))
    
    bot.send_message(
        message.chat.id, 
        f"👋 Привет! Я — твой личный копирайтер.\n\n"
        f"Выбери, что нужно написать. Я сгенерирую текст за пару секунд.\n\n"
        f"💰 Стоимость одной генерации: <b>{PRICE_STARS} Stars</b>.",
        reply_markup=markup,
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda message: message.text == "ℹ️ О боте")
def about(message):
    bot.send_message(message.chat.id, "Я генерирую тексты с помощью нейросети. Каждый запрос стоит 20 Stars.")

@bot.message_handler(func=lambda message: message.text in ["✍️ Написать пост", "📝 Сделать описание", "🎓 Написать сочинение", "📖 Написать историю"])
def choose_service(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(f"⭐ Оплатить {PRICE_STARS} Stars", pay=True)
    markup.add(btn)
    
    bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Генерация: {message.text}",
        description=f"Оплата за создание текста ({message.text})",
        invoice_payload=f"pay_{message.text}", 
        provider_token="", 
        currency="XTR", 
        prices=[types.LabeledPrice(label="Текст", amount=PRICE_STARS)],
        reply_markup=markup
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    service = message.successful_payment.invoice_payload.replace("pay_", "")
    msg = bot.send_message(message.chat.id, f"✅ Оплата получена!\nТеперь напиши тему для «{service}»:")
    bot.register_next_step_handler(msg, generate_text, service)

def generate_text(message, service):
    bot.send_chat_action(message.chat.id, 'typing')
    
    prompts = {
        "✍️ Написать пост": f"Напиши интересный пост для социальных сетей на тему: {message.text}. Используй эмодзи.",
        "📝 Сделать описание": f"Напиши продающее описание для товара: {message.text}.",
        "🎓 Написать сочинение": f"Напиши школьное сочинение на тему: {message.text}. Объем 200-300 слов.",
        "📖 Написать историю": f"Напиши короткий рассказ на тему: {message.text}."
    }
    user_prompt = prompts.get(service, f"Выполни задачу: {service}. Тема: {message.text}")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if 'choices' in data:
            answer = data['choices'][0]['message']['content']
        else:
            answer = f"Ошибка API: {data}"

        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                bot.send_message(message.chat.id, answer[i:i+4000])
        else:
            bot.send_message(message.chat.id, answer)
            
        bot.send_message(ADMIN_ID, f"💰 Продажа! @{message.from_user.username} купил {service}")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка генерации: {e}")
        bot.send_message(ADMIN_ID, f"⚠️ Ошибка API: {e}")

if __name__ == "__main__":
    print("🚀 Контент-бот запущен.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
