# UptimeRobot + Render: Bot 24/7 Ishlashi

## 1. Botni Render'ga tayyorlash

### main.py ni yangilang (health check endpoint qo'shing):
```python
import sys
import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
import threading

# Environment variable dan token olish
API_TOKEN = os.environ.get('BOT_TOKEN', "8403878780:AAGebqROs5PhBejKf5alU4lBwL-JNG-0pWs")
PORT = int(os.environ.get('PORT', 8000))

BASE_URLS = {
    "10m": "https://sv9.api999api.com/google/api.php",
    "12h": "https://sv5.api999api.com/google/api.php"
}

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

class Form(StatesGroup):
    choosing_mode = State()
    waiting_keys = State()

# Health check endpoint
async def health_check(request):
    return web.Response(text="Bot is running! ✅", status=200)

async def create_app():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    return app

def extract_keys_from_text(text: str) -> list[str]:
    keys = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Key :"):
            parts = line.split("Key :")
            if len(parts) == 2:
                keys.append(parts[1].strip())
        elif line and not line.startswith("Link Tool") and "http" not in line:
            keys.append(line)
    return keys

def format_emails_monospace(emails: list[str]) -> str:
    lines = [f"{i+1} - `{email}`" for i, email in enumerate(emails)]
    lines.append(f"\n`AKA999aka`")
    return "\n".join(lines)

async def get_email_from_key(session: aiohttp.ClientSession, key: str, minutes: int, base_url: str) -> str | None:
    url = f"{base_url}?key_value={key}&timelive={minutes}"
    for attempt in range(5):
        try:
            async with session.get(url, timeout=30) as resp:
                text = await resp.text()
                print(f"Ответ API для {key}:\n{text}\n")
                if "@" in text:
                    email = text.strip().split("|")[0]
                    return email
        except Exception as e:
            print(f"[ERROR] попытка {attempt+1} для ключа {key}: {e}")
        await asyncio.sleep(1)
    return None

@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Почты на 10 минут", callback_data="mode_10m")
    builder.button(text="📬 Почты на 12 часов", callback_data="mode_12h")
    builder.adjust(2)

    await state.set_state(Form.choosing_mode)
    await message.answer(
        "Привет! Выбери тип почты, которую хочешь получить:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("mode_"))
async def mode_selected(callback: types.CallbackQuery, state: FSMContext):
    mode = callback.data.replace("mode_", "")
    await state.update_data(mode=mode)
    await state.set_state(Form.waiting_keys)

    await callback.message.answer(
        "Отправь список ключей (каждый с новой строки) или текст с ключами в формате:\n`Key : <ключ>`",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@dp.message(Form.waiting_keys)
async def handle_keys(message: Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode", "10m")
    minutes = 10 if mode == "10m" else 720
    base_url = BASE_URLS.get(mode, BASE_URLS["10m"])

    keys = extract_keys_from_text(message.text)
    if not keys:
        await message.answer("❌ Не найдено ни одного ключа. Попробуй снова.")
        return

    async with aiohttp.ClientSession() as session:
        emails = []
        failed = []

        for key in keys:
            email = await get_email_from_key(session, key, minutes, base_url)
            if email:
                emails.append(email)
            else:
                failed.append(key)

    if emails:
        await message.answer(format_emails_monospace(emails))
    if failed:
        await message.answer("❌ Не удалось получить почты для ключей:\n" + "\n".join(failed))

    await cmd_start(message, state)

async def start_web_server():
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def main():
    print("Bot va web server ishga tushmoqda...")
    
    # Web serverni alohida taskda ishga tushirish
    asyncio.create_task(start_web_server())
    
    # Bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")
```

### requirements.txt:
```txt
aiogram>=3.0.0
aiohttp>=3.8.0
```

## 2. Render'da deploy qilish

1. **GitHub'ga kod yuklang**
2. **Render.com'da Web Service yarating**
3. **Sozlamalar:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
   - Environment Variable: `BOT_TOKEN = your_token`

4. **Deploy tugagach URL oling**, masalan:
   `https://your-bot-name.onrender.com`

## 3. UptimeRobot sozlash

### 3.1. Ro'yxatdan o'tish
1. [uptimerobot.com](https://uptimerobot.com) ga kiring
2. **"Sign up for FREE!"** tugmasini bosing
3. Email va parol kiriting

### 3.2. Monitor yaratish
1. Dashboard'da **"Add New Monitor"** tugmasini bosing

2. **Monitor sozlamalari:**
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Telegram Bot Monitor`
   - **URL**: `https://your-bot-name.onrender.com/health`
   - **Monitoring Interval**: `5 minutes` (bepul max)

3. **Alert Contacts** (ixtiyoriy):
   - Email manzil qo'shing
   - Agar bot ishlamasa, xabar keladi

4. **"Create Monitor"** tugmasini bosing

### 3.3. Natija tekshirish
- **Status**: 🟢 UP ko'rsatishi kerak
- **Response Time**: 200-500ms orasida bo'lishi kerak
- **Uptime**: 100% bo'lishi kerak

## 4. Ishlashini tekshirish

### Bot tekshiruvi:
1. Telegram'da botga `/start` yuboring
2. Javob tezligi normal bo'lishi kerak (1-2 sekund)

### Monitor tekshiruvi:
1. UptimeRobot dashboard'da "UP" holatini ko'ring
2. Response time grafigini kuzating

### Render logs:
```
Bot va web server ishga tushmoqda...
Web server started on port 10000
Bot ishga tushmoqda...
```

## 5. Qo'shimcha sozlamalar

### UptimeRobot bepul limits:
- **50 ta monitor** (bizga 1 ta kerak)
- **5 daqiqalik interval** (yetarli)
- **2 oy log saqlash**

### Render bepul limits:
- **750 soat/oy** (31 kun)
- **512MB RAM**
- **Disk: 1GB**

## 6. Muammolarni hal qilish

### Agar bot sekin javob bersa:
1. UptimeRobot monitoringni tekshiring
2. Render logs'da xatolarni qidiring
3. Health endpoint ishyotganini tekshiring: `your-url.onrender.com/health`

### Agar UptimeRobot "DOWN" ko'rsatsa:
1. URL to'g'ri ekanligini tekshiring
2. Render service'i ishyotganini tekshiring
3. Health endpoint 200 status qaytaryotganini tekshiring

## 7. Monitoring Dashboard

UptimeRobot sizga beradi:
- **Real-time status**
- **Uptime statistikasi**
- **Response time grafiklari**
- **Downtime alerts**

Bu kombinatsiya bilan botingiz 24/7 ishlaydi va hech qachon "uxlamaydi"! 🚀