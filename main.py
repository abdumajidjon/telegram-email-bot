import sys
import os
import asyncio
import aiohttp
import json
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Environment variable dan token olish
API_TOKEN = os.environ.get('BOT_TOKEN', "8403878780:AAGebqROs5PhBejKf5alU4lBwL-JNG-0pWs")
PORT = int(os.environ.get('PORT', 8000))
ADMIN_ID = 976525232  # Sizning Telegram ID

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

# In-memory database
users_db = {}
pending_users = {}

class Form(StatesGroup):
    choosing_mode = State()
    waiting_keys = State()
    waiting_contact = State()

class AdminStates(StatesGroup):
    viewing_stats = State()

# Health check endpoint
async def health_check(request):
    return web.Response(text="Bot is running! ✅", status=200)

async def create_app():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    return app

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def is_approved_user(user_id: int) -> bool:
    return str(user_id) in users_db and users_db[str(user_id)]['status'] == 'approved'

def save_user(user_id: int, user_data: dict):
    users_db[str(user_id)] = user_data

def get_stats():
    total_users = len(users_db)
    approved_users = len([u for u in users_db.values() if u['status'] == 'approved'])
    pending_users_count = len(pending_users)
    return {
        'total': total_users,
        'approved': approved_users,
        'pending': pending_users_count
    }

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
    user_id = message.from_user.id
    
    # Admin uchun
    if is_admin(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📩 Botdan foydalanish", callback_data="use_bot")]
        ])
        await message.answer(
            "🔧 *Admin Panel*\n\nSalom admin! Nima qilmoqchisiz?",
            reply_markup=keyboard
        )
        return
    
    # Tasdiqlangan foydalanuvchi uchun
    if is_approved_user(user_id):
        builder = InlineKeyboardBuilder()
        builder.button(text="📩 Pochta 10 minut", callback_data="mode_10m")
        builder.button(text="📬 Pochta 12 soat", callback_data="mode_12h")
        builder.adjust(2)

        await state.set_state(Form.choosing_mode)
        await message.answer(
            "✅ *Xush kelibsiz!*\n\nSiz tasdiqlangan foydalanuvchisiz. Pochta turini tanlang:",
            reply_markup=builder.as_markup()
        )
        return
    
    # Yangi foydalanuvchi - ro'yxatdan o'tish
    if str(user_id) not in users_db:
        contact_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Kontakt ulashish", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await state.set_state(Form.waiting_contact)
        await message.answer(
            "👋 *Salom!*\n\n"
            "Bu bot faqat ro'yxatdan o'tgan foydalanuvchilar uchun.\n\n"
            "Davom etish uchun kontaktingizni ulashing 👇",
            reply_markup=contact_keyboard
        )
    else:
        # Kutilayotgan foydalanuvchi
        await message.answer(
            "⏳ *Kutilmoqda...*\n\n"
            "Sizning so'rovingiz admin tomonidan ko'rib chiqilmoqda.\n"
            "Tasdiqlangandan keyin xabar olasiz."
        )

@dp.message(Form.waiting_contact, F.contact)
async def handle_contact(message: Message, state: FSMContext):
    user_id = message.from_user.id
    contact = message.contact
    
    # Foydalanuvchi ma'lumotlarini saqlash
    user_data = {
        'user_id': user_id,
        'first_name': message.from_user.first_name or "Noma'lum",
        'last_name': message.from_user.last_name or "",
        'username': message.from_user.username or "Yo'q",
        'phone': contact.phone_number,
        'status': 'pending',
        'registered_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    pending_users[str(user_id)] = user_data
    
    # Admin'ga xabar yuborish
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user_id}")
        ]
    ])
    
    admin_message = (
        f"👤 *Yangi foydalanuvchi so'rovi*\n\n"
        f"👨‍💼 Ism: {user_data['first_name']} {user_data['last_name']}\n"
        f"🆔 Username: @{user_data['username']}\n"
        f"📱 Telefon: {user_data['phone']}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📅 Vaqt: {user_data['registered_at']}"
    )
    
    try:
        await bot.send_message(ADMIN_ID, admin_message, reply_markup=admin_keyboard)
        await message.answer(
            "✅ *So'rov yuborildi!*\n\n"
            "Sizning ma'lumotlaringiz admin'ga yuborildi.\n"
            "Tasdiqlangandan keyin xabar olasiz.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        print(f"Admin'ga xabar yuborishda xatolik: {e}")
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    await state.clear()

# Admin callback handlers
@dp.callback_query(F.data == "admin_users")
async def admin_users_list(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    if not users_db:
        await callback.message.answer("📝 Hozircha foydalanuvchilar yo'q.")
        await callback.answer()
        return
    
    users_text = "👥 *Barcha foydalanuvchilar:*\n\n"
    for i, (user_id, user_data) in enumerate(users_db.items(), 1):
        status_emoji = "✅" if user_data['status'] == 'approved' else "❌"
        users_text += (
            f"{i}. {status_emoji} {user_data['first_name']} {user_data['last_name']}\n"
            f"   @{user_data['username']} | {user_data['phone']}\n"
            f"   ID: `{user_id}` | {user_data['registered_at']}\n\n"
        )
    
    # Pending users
    if pending_users:
        users_text += "\n⏳ *Kutilayotgan foydalanuvchilar:*\n\n"
        for i, (user_id, user_data) in enumerate(pending_users.items(), 1):
            users_text += (
                f"{i}. ⏳ {user_data['first_name']} {user_data['last_name']}\n"
                f"   @{user_data['username']} | {user_data['phone']}\n"
                f"   ID: `{user_id}` | {user_data['registered_at']}\n\n"
            )
    
    await callback.message.answer(users_text[:4000])  # Telegram limit
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_statistics(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    stats = get_stats()
    stats_text = (
        f"📊 *Bot Statistikasi*\n\n"
        f"👥 Jami foydalanuvchilar: {stats['total']}\n"
        f"✅ Tasdiqlangan: {stats['approved']}\n"
        f"⏳ Kutilayotgan: {stats['pending']}\n"
        f"❌ Rad etilgan: {stats['total'] - stats['approved']}\n\n"
        f"📅 Hozirgi vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await callback.message.answer(stats_text)
    await callback.answer()

@dp.callback_query(F.data == "use_bot")
async def admin_use_bot(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Pochta 10 minut", callback_data="mode_10m")
    builder.button(text="📬 Pochta 12 soat", callback_data="mode_12h")
    builder.adjust(2)

    await state.set_state(Form.choosing_mode)
    await callback.message.answer(
        "Admin sifatida bot funksiyalaridan foydalanasiz:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    user_id = callback.data.split("_")[1]
    
    if user_id not in pending_users:
        await callback.answer("Foydalanuvchi topilmadi!")
        return
    
    # Pending'dan olib, approved qilish
    user_data = pending_users[user_id]
    user_data['status'] = 'approved'
    user_data['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_user(int(user_id), user_data)
    del pending_users[user_id]
    
    # Foydalanuvchiga xabar yuborish
    try:
        await bot.send_message(
            int(user_id),
            "🎉 *Tabriklaymiz!*\n\n"
            "Sizning so'rovingiz tasdiqlandi!\n"
            "Endi botdan foydalanishingiz mumkin.\n\n"
            "Boshlash uchun: /start"
        )
    except Exception as e:
        print(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
    
    # Admin'ga tasdiqlash
    await callback.message.edit_text(
        f"✅ *Foydalanuvchi tasdiqlandi*\n\n"
        f"👨‍💼 {user_data['first_name']} {user_data['last_name']}\n"
        f"📱 {user_data['phone']}\n"
        f"🆔 ID: `{user_id}`"
    )
    await callback.answer("✅ Foydalanuvchi tasdiqlandi!")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    user_id = callback.data.split("_")[1]
    
    if user_id not in pending_users:
        await callback.answer("Foydalanuvchi topilmadi!")
        return
    
    user_data = pending_users[user_id]
    user_data['status'] = 'rejected'
    user_data['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_user(int(user_id), user_data)
    del pending_users[user_id]
    
    # Foydalanuvchiga xabar yuborish
    try:
        await bot.send_message(
            int(user_id),
            "❌ *Afsuski...*\n\n"
            "Sizning so'rovingiz rad etildi.\n"
            "Qo'shimcha ma'lumot uchun admin bilan bog'laning."
        )
    except Exception as e:
        print(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
    
    # Admin'ga tasdiqlash
    await callback.message.edit_text(
        f"❌ *Foydalanuvchi rad etildi*\n\n"
        f"👨‍💼 {user_data['first_name']} {user_data['last_name']}\n"
        f"📱 {user_data['phone']}\n"
        f"🆔 ID: `{user_id}`"
    )
    await callback.answer("❌ Foydalanuvchi rad etildi!")

@dp.callback_query(F.data.startswith("mode_"))
async def mode_selected(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Ruxsat tekshirish
    if not is_admin(user_id) and not is_approved_user(user_id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    mode = callback.data.replace("mode_", "")
    await state.update_data(mode=mode)
    await state.set_state(Form.waiting_keys)

    await callback.message.answer(
        "Kalitlar ro'yxatini yuboring (har bir kalit yangi qatorda) yoki ushbu formatda:\n`Key : <kalit>`",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@dp.message(Form.waiting_keys)
async def handle_keys(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Ruxsat tekshirish
    if not is_admin(user_id) and not is_approved_user(user_id):
        await message.answer("❌ Sizda ruxsat yo'q!")
        return
    
    data = await state.get_data()
    mode = data.get("mode", "10m")
    minutes = 10 if mode == "10m" else 720
    base_url = BASE_URLS.get(mode, BASE_URLS["10m"])

    keys = extract_keys_from_text(message.text)
    if not keys:
        await message.answer("❌ Hech qanday kalit topilmadi. Qayta urinib ko'ring.")
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
        await message.answer("❌ Ushbu kalitlar uchun pochta olinmadi:\n" + "\n".join(failed))

    # Admin uchun qayta menu
    if is_admin(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📩 Botdan foydalanish", callback_data="use_bot")]
        ])
        await message.answer("🔧 *Admin Panel*", reply_markup=keyboard)
    else:
        # Oddiy foydalanuvchi uchun
        builder = InlineKeyboardBuilder()
        builder.button(text="📩 Pochta 10 minut", callback_data="mode_10m")
        builder.button(text="📬 Pochta 12 soat", callback_data="mode_12h")
        builder.adjust(2)
        await message.answer("Yana pochta kerakmi?", reply_markup=builder.as_markup())

    await state.set_state(Form.choosing_mode)

async def start_web_server():
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def main():
    print("Bot va web server ishga tushmoqda...")
    print(f"Admin ID: {ADMIN_ID}")
    
    # Web serverni alohida taskda ishga tushirish
    asyncio.create_task(start_web_server())
    
    # Bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")
