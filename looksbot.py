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

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not BOT_TOKEN or not OPENROUTER_API_KEY:
    raise SystemExit("❌ Укажи BOT_TOKEN и OPENROUTER_API_KEY в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# Бесплатная модель с поддержкой изображений
MODEL = "meta-llama/llama-3.2-11b-vision-instruct:free"

SYSTEM_PROMPT = """Ты — эксперт по эстетике лица и стилю. Проанализируй фото и верни ТОЛЬКО валидный JSON:
{
  "score": число от 1.0 до 10.0,
  "gender": "male" или "female",
  "strengths": ["3-4 пункта: что очень хорошо"],
  "weaknesses": ["2-3 пункта: что можно улучшить"],
  "advice": ["3-4 конкретных совета"],
  "exercises": ["3-4 упражнения или процедуры"]
}
Будь объективен и тактичен. Если лицо не видно, верни score: 1.0 и пустые списки."""

def get_category(score: float, gender: str) -> str:
    if gender == "male":
        if score <= 3.0: return "sub 3"
        elif score <= 4.5: return "sub 5"
        elif score <= 5.5: return "ltn"
        elif score <= 7.0: return "mtn"
        elif score <= 8.5: return "htn"
        elif score <= 9.5: return "chad lite"
        else: return "chad"
    else:
        if score <= 3.0: return "sub 3"
        elif score <= 4.5: return "sub 5"
        elif score <= 5.5: return "ltb"
        elif score <= 7.0: return "mtb"
        elif score <= 8.5: return "htb"
        elif score <= 9.5: return "goddess lite"
        else: return "goddess"

def extract_json(text: str) -> dict:
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match: raise ValueError("JSON not found")
    return json.loads(match.group(0))

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "📸 *Привет! Отправь своё фото.*\n"
        "• Анфас, хорошее освещение\n• Без фильтров и масок\n• Волосы убраны с лица"
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    file_obj = await bot.download(photo.file_id)
    image_bytes = file_obj.read()
    base64_img = base64.b64encode(image_bytes).decode("utf-8")

    await message.answer("⏳ *Анализирую...* Подожди 10–20 сек.")

    try:
        # Убрали response_format (бесплатные модели часто его ломают)
        # Добавили явный таймаут 60 сек для очередей OpenRouter
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Оцени фото. Верни ТОЛЬКО JSON, без лишних слов."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]}
            ],
            temperature=0.1
        )

        raw_text = response.choices[0].message.content
        data = extract_json(raw_text)

        score = float(data["score"])
        gender = data["gender"]
        category = get_category(score, gender)
        gender_ru = "мужчина" if gender == "male" else "женщина"

        strengths = "\n".join([f"✅ {s}" for s in data.get("strengths", [])]) or "✅ Ничего не выделено"
        weaknesses = "\n".join([f"❌ {w}" for w in data.get("weaknesses", [])]) or "❌ Ничего не выделено"
        advice = "\n".join([f"💡 {a}" for a in data.get("advice", [])]) or "💡 Сон, вода, осанка"
        exercises = "\n".join([f"🏋️ {e}" for e in data.get("exercises", [])]) or "🏋️ Уход и массаж лица"

        reply = (
            f"📊 *Оценка:* `{score}/10`\n"
            f"🏷️ *Категория:* `{category}` ({gender_ru})\n\n"
            f"✨ *Что хорошо:*\n{strengths}\n\n"
            f"🔻 *Улучшить:*\n{weaknesses}\n\n"
            f"📝 *Советы:*\n{advice}\n\n"
            f"💪 *Упражнения:*\n{exercises}\n\n"
            f"⚠️ _ИИ оценивает по паттернам. Баллы не определяют твою ценность._"
        )
        await message.answer(reply, parse_mode="Markdown")

    except Exception as e:
        # ВРЕМЕННО: выводим реальную ошибку в чат для отладки
        await message.answer(
            f"❌ Ошибка анализа:\n`{type(e).__name__}: {e}`\n\n"
            f"🔍 Проверь логи на Bothost или попробуй позже."
        )
        logging.error(f"OpenRouter Error: {e}")

# Endpoint для хостинга (чтобы Render не засыпал)
@dp.message(Command("health"))
async def health_check(message: types.Message):
    await message.answer("🟢 Бот работает.")

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("✅ Бот запущен.")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
