import os, json, base64, asyncio, logging, re
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

# Бесплатные модели OpenRouter (пробуй по очереди)
MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.0-flash-thinking-exp:free",
    "google/gemini-exp-1206:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "meta-llama/llama-3.2-11b-vision-instruct:free",
]

current_model_index = 0

SYSTEM_PROMPT = """Оцени внешность человека на фото по шкале 1-10. 
Верни ТОЛЬКО JSON, без пояснений, без markdown:
{"score":7.5,"gender":"male","strengths":["глаза","улыбка"],"weaknesses":["нос"],"advice":["спорт"],"exercises":["мьюинг"]}"""

def extract_json(text):
    text = text.replace('```json', '').replace('```', '')
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
        
        # Пробуем текущую модель
        model = MODELS[current_model_index]
        print(f"🤖 Использую модель: {model}")
        
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
        print(f"✅ Ответ: {raw_text}")
        
        data = extract_json(raw_text)
        
        if not data:
            await msg.edit_text("❌ Не удалось проанализировать фото. Попробуй другое.")
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
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Ошибка: {error_msg}")
        
        if "402" in error_msg or "429" in error_msg:
            # Меняем модель на следующую
            current_model_index = (current_model_index + 1) % len(MODELS)
            await msg.edit_text(f"🔄 Лимит исчерпан. Пробую другую модель... Отправь фото ещё раз.")
        else:
            await msg.edit_text(f"❌ Ошибка: {error_msg[:100]}")

async def main():
    print("🟢 Бот запущен (OpenRouter)")
    print(f"📋 Доступно моделей: {len(MODELS)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
