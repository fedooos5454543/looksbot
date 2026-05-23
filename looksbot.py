import os, json, asyncio, logging, re, io
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN:
    print("❌ Нет BOT_TOKEN в .env")
    exit()
if not GEMINI_API_KEY:
    print("❌ Нет GEMINI_API_KEY в .env")
    exit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настраиваем Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

SYSTEM_PROMPT = """Оцени внешность человека на фото по шкале 1-10. 
Верни ТОЛЬКО JSON, без пояснений:
{"score": 7.5, "gender": "male", "strengths": ["глаза", "улыбка"], "weaknesses": ["нос"], "advice": ["спорт"], "exercises": ["мьюинг"]}"""

def extract_json(text):
    # Убираем markdown
    text = text.replace('```json', '').replace('```', '')
    # Ищем JSON
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
    print("📸 Получено фото")
    msg = await message.answer("⏳ Анализирую фото...")

    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file = await bot.download(photo.file_id)
        image_bytes = file.read()
        
        # Открываем через PIL
        image = Image.open(io.BytesIO(image_bytes))
        
        # Отправляем в Gemini
        response = model.generate_content([SYSTEM_PROMPT, image])
        raw_text = response.text
        
        print(f"Ответ Gemini: {raw_text}")
        
        # Парсим JSON
        data = extract_json(raw_text)
        
        if not data:
            await msg.edit_text("❌ Не удалось проанализировать фото. Попробуй другое.")
            return
        
        # Получаем данные
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
        
        # Формируем ответ
        result = (
            f"📊 **Оценка:** `{score}/10`\n"
            f"🏷️ **Категория:** `{category}` ({gender_text})\n\n"
            f"✅ **Сильные стороны:**\n{chr(10).join(f'• {s}' for s in strengths)}\n\n"
            f"🔻 **Слабые стороны:**\n{chr(10).join(f'• {w}' for w in weaknesses)}\n\n"
            f"💡 **Советы:**\n{chr(10).join(f'• {a}' for a in advice)}\n\n"
            f"🏋️ **Упражнения:**\n{chr(10).join(f'• {e}' for e in exercises)}"
        )
        
        await msg.edit_text(result, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        await msg.edit_text(f"❌ Произошла ошибка: {e}")

async def main():
    print("🟢 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
