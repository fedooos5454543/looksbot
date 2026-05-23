import os, json, base64, asyncio, logging, re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from openai import AsyncOpenAI
from openai import APITimeoutError, APIConnectionError, APIStatusError
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not BOT_TOKEN or not OPENROUTER_API_KEY:
    raise SystemExit("❌ Нет токенов в .env / переменных Bothost")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    timeout=60.0
)

# ✅ Более стабильная модель для анализа фото
MODEL = "google/gemini-2.0-flash-001"  # Gemini лучше работает с фото и JSON

SYSTEM_PROMPT = """Ты эксперт по оценке внешности. Проанализируй фото и верни ТОЛЬКО валидный JSON, без markdown, без пояснений, только объект JSON:

{
  "score": 7.5,
  "gender": "male",
  "strengths": ["красивые глаза", "симметричное лицо"],
  "weaknesses": ["небольшая асимметрия губ"],
  "advice": ["улучшить осанку", "больше улыбаться"],
  "exercises": ["мьюинг", "массаж лица"]
}

ВАЖНО: верни ТОЛЬКО JSON объект, ничего больше."""

def extract_json(text: str) -> dict:
    """Улучшенное извлечение JSON из ответа модели"""
    # Убираем markdown блоки
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Ищем JSON объект (поддерживает вложенные фигурные скобки)
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
                if not stack and start != -1:
                    json_str = text[start:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        # Если не получилось, продолжаем искать
                        start = -1
                        continue
    
    # Если не нашли, пробуем найти хоть что-то похожее на JSON
    m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
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
    await m.answer("📸 Отправь фото анфас. Анализ займёт 10-30 сек.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    print("🔍 [DEBUG] Фото получено, начинаю анализ...")
    status_msg = await message.answer("⏳ *Анализирую...* Это может занять до 30 секунд.", parse_mode="Markdown")

    try:
        # Получаем фото
        photo = message.photo[-1]
        file = await bot.download(photo.file_id)
        image_data = file.read()
        
        # Конвертируем в base64
        b64 = base64.b64encode(image_data).decode()

        print(f"📸 [DEBUG] Размер фото: {len(image_data)} байт")

        # Отправляем запрос к OpenRouter
        resp = await client.chat.completions.create(
            model=MODEL,
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

        raw = resp.choices[0].message.content
        print(f"✅ [DEBUG] Ответ ИИ (полный):\n{raw}")
        
        data = extract_json(raw)
        
        if not data:
            await status_msg.edit_text("❌ Не удалось распознать ответ. Попробуй другое фото.")
            print(f"⚠️ [DEBUG] Не удалось извлечь JSON из: {raw[:200]}")
            return

        # Проверяем обязательные поля
        score = float(data.get("score", 5.0))
        gender = data.get("gender", "male")
        
        # Валидация пола
        if gender not in ["male", "female"]:
            gender = "male"
        
        cat = get_category(score, gender)
        gr = "мужчина" if gender == "male" else "женщина"

        # Формируем ответ
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

    except APITimeoutError:
        await status_msg.edit_text("⏳ Таймаут. Сервер OpenRouter перегружен. Попробуй через 2 минуты.")
        logging.warning("OpenRouter Timeout")
    except APIConnectionError as e:
        await status_msg.edit_text("🌐 Нет связи с API. Проверь ключ или хостинг.")
        logging.error(f"Connection: {e}")
    except APIStatusError as e:
        await status_msg.edit_text(f"❌ Ошибка API {e.status_code}. Попробуй другую модель или позже.")
        logging.error(f"Status {e.status_code}: {e.body}")
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"💥 [DEBUG] CRASH:\n{err}")
        await status_msg.edit_text(f"❌ Ошибка: {type(e).__name__}\nПроверь логи бота.")
        logging.error(err)

async def main():
    print("🟢 БОТ ЗАПУЩЕН. ВЕРСИЯ: FIXED-3")
    print(f"🤖 Модель: {MODEL}")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
