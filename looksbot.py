import os, json, base64, asyncio, logging, re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Получи ключ тут: https://aistudio.google.com/apikey

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise SystemExit("❌ Нет токенов в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настраиваем Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

SYSTEM_PROMPT = """Проанализируй фото человека и верни ТОЛЬКО JSON объект, без markdown, без пояснений:

{
  "score": 7.5,
  "gender": "male",
  "strengths": ["красивые глаза", "симметричное лицо"],
  "weaknesses": ["небольшая асимметрия губ"],
  "advice": ["улучшить осанку", "больше улыбаться"],
  "exercises": ["мьюинг", "массаж лица"]
}

Оценивай по шкале 1-10. Gender: "male" или "female". Верни ТОЛЬКО JSON."""

def extract_json(text: str) -> dict:
    """Извлечение JSON из ответа"""
    # Убираем markdown блоки
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Ищем JSON объект
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except:
            pass
    return {}

def get_category(s, g):
    if g == "male":
        if s <= 3: return "sub 3"
        elif s <= 4.5: return "sub 5"
        elif s <= 5.5: return "ltn"
        elif s <= 7: return "mtn"
        elif s <= 8.5: return "htn"
        elif s <= 9.5: return "chad lite"
        return "chad"
    else:
        if s <= 3: return "sub 3"
        elif s <= 4.5: return "sub 5"
        elif s <= 5.5: return "ltb"
        elif s <= 7: return "mtb"
        elif s <= 8.5: return "htb"
        elif s <= 9.5: return "goddess lite"
        return "goddess"

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("📸 Отправь фото анфас. Анализ займёт 5-15 сек.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    print("🔍 [DEBUG] Фото получено...")
    status_msg = await message.answer("⏳ *Анализирую...*", parse_mode="Markdown")

    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file = await bot.download(photo.file_id)
        image_data = file.read()
        
        print(f"📸 [DEBUG] Размер фото: {len(image_data)} байт")

        # Отправляем в Gemini
        response = model.generate_content([
            SYSTEM_PROMPT,
            {"mime_type": "image/jpeg", "data": image_data}
        ])
        
        raw = response.text
        print(f"✅ [DEBUG] Ответ Gemini:\n{raw}")
        
        data = extract_json(raw)
        
        if not data:
            await status_msg.edit_text("❌ Не удалось распознать ответ. Попробуй другое фото.")
            return

        score = float(data.get("score", 5.0))
        gender = data.get("gender", "male")
        
        if gender not in ["male", "female"]:
            gender = "male"
        
        cat = get_category(score, gender)
        gr = "мужчина" if gender == "male" else "женщина"

        strengths = data.get('strengths', ['не определено'])
        weaknesses = data.get('weaknesses', ['не определено'])
        advice = data.get('advice', ['спите 8 часов'])
        exercises = data.get('exercises', ['массаж лица'])

        txt = (
            f"📊 *Оценка:* `{score}/10`\n"
            f"🏷️ *Категория:* `{cat}` ({gr})\n\n"
            f"✅ *Сильные стороны:*\n{', '.join(strengths)}\n\n"
            f"🔻 *Слабые стороны:*\n{', '.join(weaknesses)}\n\n"
            f"💡 *Советы:*\n{', '.join(advice)}\n\n"
            f"🏋️ *Упражнения:*\n{', '.join(exercises)}"
        )
        
        await status_msg.edit_text(txt, parse_mode="Markdown")

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"💥 [DEBUG] CRASH:\n{err}")
        await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}\nПроверь логи.")

async def main():
    print("🟢 БОТ ЗАПУЩЕН (Gemini)")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
