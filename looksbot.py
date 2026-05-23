import os
import json
import base64
import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from dotenv import load_dotenv
 
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
 
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
 
if not BOT_TOKEN:
    print("❌ Нет BOT_TOKEN")
    exit()
if not OPENROUTER_API_KEY:
    print("❌ Нет OPENROUTER_API_KEY")
    exit()
 
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
 
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    timeout=60.0
)
 
# Актуальные рабочие бесплатные мультимодальные модели на OpenRouter
MODELS = [
    "google/gemini-2.5-flash:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "meta-llama/llama-3.2-11b-vision-instruct:free",
    "google/gemini-2.5-pro:free"
]
 
current_model_index = 0
 
SYSTEM_PROMPT = """Оцени внешность человека на фото по шкале 1-10. 
Верни ТОЛЬКО JSON, без пояснений, без markdown:
{"score":7.5,"gender":"male","strengths":["глаза","улыбка"],"weaknesses":["нос"],"advice":["спорт"],"exercises":["мьюинг"]}"""
 
def extract_json(text):
    text = text.replace('```json', '').replace('
```', '')
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return None
 
def get_category(score, gender):
    if gender == "male":
        if score <= 3: return "sub 3"
        elif score <= 4.5: return "sub 5"
        elif score <= 5.5: return "ltn"
        elif score <= 7: return "mtn"
        elif score <= 8.5: return "htn"
        elif score <= 9.5: return "chad lite"
        return "chad"
    else:
        if score <= 3: return "sub 3"
        elif score <= 4.5: return "sub 5"
        elif score <= 5.5: return "ltb"
        elif score <= 7: return "mtb"
        elif score <= 8.5: return "htb"
        elif score <= 9.5: return "goddess lite"
        return "goddess"
 
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("📸 Привет! Отправь мне фото анфас, и я оценю твою внешность.")
 
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    global current_model_index
    
    print("📸 Получено фото")
    msg = await message.answer("⏳ Анализирую фото...")
 
    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file = await bot.download(photo.file_id)
        image_bytes = file.read()
        b64 = base64.b64encode(image_bytes).decode()
    except Exception as download_error:
        print(f"❌ Ошибка скачивания файла: {download_error}")
        await msg.edit_text("❌ Не удалось загрузить фото из Telegram. Попробуй еще раз.")
        return

    response = None
    raw_text = None
    
    # Автоматический перебор моделей прямо внутри запроса
    for attempt in range(len(MODELS)):
        model = MODELS[current_model_index]
        print(f"🤖 Попытка {attempt + 1}: Использую модель {model}")
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }],
                temperature=0.1,
                max_tokens=500
            )
            raw_text = response.choices[0].message.content
            print(f"✅ Успешный ответ от {model}")
            break # Выходим из цикла, если модель ответила успешно
            
        except Exception as api_error:
            print(f"⚠️ Ошибка модели {model}: {api_error}")
            # Сдвигаем индекс на следующую модель для будущих запросов и текущего цикла
            current_model_index = (current_model_index + 1) % len(MODELS)
            await msg.edit_text(f"⏳ Модель перегружена или недоступна. Подключаю резервный вариант...")
            await asyncio.sleep(1) # Небольшая пауза перед следующим запросом
            
    if not raw_text:
        await msg.edit_text("❌ Все бесплатные нейросети сейчас перегружены или недоступны. Попробуй позже.")
        return
        
    try:
        print(f"📝 Получен сырой текст: {raw_text}")
        data = extract_json(raw_text)
        
        if not data:
            await msg.edit_text("❌ Не удалось распознать структуру ответа нейросети. Попробуй другое фото.")
            return
        
        score = float(data.get("score", 5.0))
        gender = data.get("gender", "male")
        if gender not in ["male", "female"]:
            gender = "male"
        
        category = get_category(score, gender)
        gender_text = "мужчина" if gender == "male" else "женщина"
        
        strengths = data.get("strengths", ["нет данных"])
        weaknesses = data.get("weaknesses", ["нет данных"])
        advice = data.get("advice", ["спать 8 часов"])
        exercises = data.get("exercises", ["массаж лица"])
        
        result = (
            f"📊 **Оценка:** `{score}/10`\n"
            f"🏷️ **Категория:** `{category}` ({gender_text})\n\n"
            f"✅ **Сильные стороны:**\n{chr(10).join(f'• {s}' for s in strengths)}\n\n"
            f"🔻 **Слабые стороны:**\n{chr(10).join(f'• {w}' for w in weaknesses)}\n\n"
            f"💡 **Советы:**\n{chr(10).join(f'• {a}' for a in advice)}\n\n"
            f"🏋️ **Упражнения:**\n{chr(10).join(f'• {e}' for e in exercises)}"
        )
        
        await msg.edit_text(result, parse_mode="Markdown")
        
    except Exception as parsing_error:
        print(f"❌ Ошибка обработки JSON: {parsing_error}")
        await msg.edit_text("❌ Произошла ошибка при обработке данных. Попробуй еще раз.")
 
async def main():
    print("🟢 Бот запущен (OpenRouter)")
    print(f"📋 Доступно моделей для ротации: {len(MODELS)}")
    await dp.start_polling(bot)
 
if __name__ == "__main__":
    asyncio.run(main())
