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
    timeout=60.0  # ⬅️ Увеличили таймаут для бесплатных очередей
)

# ✅ Более стабильная бесплатная модель с поддержкой фото
MODEL = "qwen/qwen-2.5-vl-72b-instruct:free"

SYSTEM_PROMPT = """Верни ТОЛЬКО JSON:
{"score": float, "gender": "male/female", "strengths": [str], "weaknesses": [str], "advice": [str], "exercises": [str]}"""

def extract_json(text: str) -> dict:
    m = re.search(r'\{.*\}', text, re.DOTALL)
    return json.loads(m.group(0)) if m else {}

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
    await message.answer("⏳ *Анализирую...* Подожди.")

    try:
        photo = message.photo[-1]
        file = await bot.download(photo.file_id)
        b64 = base64.b64encode(file.read()).decode()

        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": SYSTEM_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]}],
            temperature=0.1
        )

        raw = resp.choices[0].message.content
        print(f"✅ [DEBUG] Ответ ИИ: {raw[:100]}...")
        data = extract_json(raw)

        score = float(data.get("score", 5.0))
        gender = data.get("gender", "male")
        cat = get_category(score, gender)
        gr = "мужчина" if gender == "male" else "женщина"

        txt = (
            f"📊 `{score}/10` | 🏷️ `{cat}` ({gr})\n\n"
            f"✅ {', '.join(data.get('strengths', ['нет']))}\n"
            f"🔻 {', '.join(data.get('weaknesses', ['нет']))}\n"
            f"💡 {', '.join(data.get('advice', ['спите 8ч']))}\n"
            f"🏋️ {', '.join(data.get('exercises', ['массаж лица']))}"
        )
        await message.answer(txt, parse_mode="Markdown")

    except APITimeoutError:
        await message.answer("⏳ Таймаут. Сервер OpenRouter перегружен. Попробуй через 2 мин.")
        logging.warning("OpenRouter Timeout")
    except APIConnectionError as e:
        await message.answer("🌐 Нет связи с API. Проверь ключ или хостинг.")
        logging.error(f"Connection: {e}")
    except APIStatusError as e:
        await message.answer(f"❌ API вернул статус {e.status_code}: `{e.message}`")
        logging.error(f"Status {e.status_code}: {e.body}")
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"💥 [DEBUG] CRASH:\n{err}")
        await message.answer(f"❌ Ошибка:\n`{type(e).__name__}: {e}`\n📝 Логи в консоли Bothost")
        logging.error(err)

async def main():
    print("🟢 БОТ ЗАПУЩЕН. ВЕРСИЯ: DEBUG-2")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
