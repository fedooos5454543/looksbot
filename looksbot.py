import os, json, base64, asyncio, logging, re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    raise SystemExit("❌ Нет токенов в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ✅ Правильная модель Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')  # <-- ИСПРАВЛЕНО

SYSTEM_PROMPT = """Проанализируй фото человека и верни ТОЛЬКО JSON объект, без markdown:

{
  "score": 7.5,
  "gender": "male",
  "strengths": ["красивые глаза"],
  "weaknesses": ["небольшая асимметрия"],
  "advice": ["улучшить осанку"],
  "exercises": ["мьюинг"]
}
Оценивай 1-10. Gender: male или female. ТОЛЬКО JSON."""

def extract_json(text: str) -> dict:
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Ищем JSON с вложенными скобками
    stack = []
    start = -1
    for i, char in enumerate(text):
        if char == '{':
            if not stack:
                start = i
            stack.append(char)
        elif char == '}':
            if stack:
                stack.pop()
                if not stack:
                    try:
                        return json.loads(text[start:i+1])
                    except:
                        continue
    
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
    await m.answer("📸 Отправь фото анфас для анализа")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    print("🔍 Получено фото")
    status_msg = await message.answer("⏳ Анализирую...")

    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file = await bot.download(photo.file_id)
        image_data = file.read()
        
        print(f"📸 Размер: {len(image_data)} байт")

        # ✅ Правильный формат для Gemini 1.5
        import PIL.Image
        import io
        
        image = PIL.Image.open(io.BytesIO(image_data))
        
        response = model.generate_content([SYSTEM_PROMPT, image])
        
        raw = response.text
        print(f"✅ Ответ:\n{raw}")
        
        data = extract_json(raw)
        
        if not data:
            await status_msg.edit_text("❌ Не удалось обработать ответ. Попробуй другое фото.")
            print(f"⚠️ Не распарсили JSON: {raw[:200]}")
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
        print(f"💥 Ошибка:\n{err}")
        await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}")

async def main():
    print("🟢 Бот запущен (Gemini 1.5 Flash)")
    
    # Проверяем доступные модели
    try:
        models = genai.list_models()
        print("📋 Доступные модели:")
        for m in models:
            if 'gemini' in m.name:
                print(f"  - {m.name}")
    except Exception as e:
        print(f"⚠️ Не удалось получить список моделей: {e}")
    
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
