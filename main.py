admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_ticket_{ticket_id}")],
        [InlineKeyboardButton(text="✅ Yopish", callback_data=f"close_ticket_{ticket_id}")]
    ])
    
    admin_message = (
        f"🎫 *Yangi support tiket*\n\n"
        f"👤 Foydalanuvchi: {ticket_data['user_name']}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📋 Kategoriya: {category_names.get(category, 'Noma\'lum')}\n"
        f"📅 Vaqt: {ticket_data['created_at']}\n"
        f"🆔 Tiket ID: `{ticket_id}`\n\n"
        f"💬 *Xabar:*\n{message.text or 'Media fayl yuborilgan'}"
    )
    
    try:
        # Forward message to admin
        if message.text:
            await bot.send_message(ADMIN_ID, admin_message, reply_markup=admin_keyboard)
        else:
            # Forward media
            await message.forward(ADMIN_ID)
            await bot.send_message(ADMIN_ID, admin_message, reply_markup=admin_keyboard)
        
        await message.answer(
            f"✅ *Xabaringiz yuborildi!*\n\n"
            f"🆔 Tiket ID: `{ticket_id}`\n"
            f"📋 Kategoriya: {category_names.get(category)}\n"
            f"⏱️ Admin odatda 24 soat ichida javob beradi.\n\n"
            f"Javob kelganda sizga xabar beramiz."
        )
        
    except Exception as e:
        print(f"Support ticket yuborishda xatolik: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qayta urinib ko'ring.")
    
    await state.clear()

# Admin callback handlers
@dp.callback_query(F.data == "admin_users")
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    if not users_db and not pending_users:
        await callback.message.answer("📝 Hozircha foydalanuvchilar yo'q.")
        await callback.answer()
        return
    
    users_text = "👥 *Barcha foydalanuvchilar*\n\n"
    
    # Approved users
    approved_users = [(uid, data) for uid, data in users_db.items() if data['status'] == 'approved']
    if approved_users:
        users_text += "✅ *Tasdiqlangan:*\n"
        for i, (user_id, user_data) in enumerate(approved_users, 1):
            history_count = len(user_history.get(user_id, []))
            users_text += (
                f"{i}. {user_data['first_name']} {user_data['last_name']}\n"
                f"   @{user_data['username']} | {user_data['phone']}\n"
                f"   ID: `{user_id}` | 📊 {history_count} ta faoliyat\n\n"
            )
    
    # Pending users
    if pending_users:
        users_text += "\n⏳ *Kutilayotgan:*\n"
        for i, (user_id, user_data) in enumerate(pending_users.items(), 1):
            users_text += (
                f"{i}. {user_data['first_name']} {user_data['last_name']}\n"
                f"   @{user_data['username']} | {user_data['phone']}\n"
                f"   ID: `{user_id}` | {user_data.get('registered_at', 'N/A')}\n\n"
            )
    
    # Rejected users
    rejected_users = [(uid, data) for uid, data in users_db.items() if data['status'] == 'rejected']
    if rejected_users:
        users_text += "\n❌ *Rad etilgan:*\n"
        for i, (user_id, user_data) in enumerate(rejected_users, 1):
            users_text += (
                f"{i}. {user_data['first_name']} {user_data['last_name']}\n"
                f"   @{user_data['username']} | ID: `{user_id}`\n\n"
            )
    
    # Split long messages
    if len(keys) > 50:
        await message.answer(f"❌ Maksimal 50 ta kalit. Sizda {len(keys)} ta.\n\nFayl yuklash funksiyasidan foydalaning!")
        return

    # Processing message with progress
    processing_msg = await message.answer(
        f"⚡ *Email olish boshlanmoqda...*\n\n"
        f"📊 Kalitlar: {len(keys)} ta\n"
        f"🚀 Tez rejim: Parallel processing\n"
        f"⏱️ Taxminiy vaqt: {len(keys) * 0.4:.1f} sekund\n\n"
        f"⏳ Iltimos kuting..."
    )
    
    try:
        # Use optimized parallel processing
        emails, failed = await get_multiple_emails_parallel(keys, minutes, base_url)
        
        # Save to history
        mode_name = "10 daqiqa" if mode == "10m" else "12 soat"
        save_user_history(user_id, len(keys), len(emails), mode)
        
        # Delete processing message
        await processing_msg.delete()
        
        if emails:
            # Split emails into chunks if too many
            if len(emails) > 20:
                chunks = [emails[i:i+20] for i in range(0, len(emails), 20)]
                for i, chunk in enumerate(chunks):
                    chunk_text = format_emails_monospace(chunk)
                    await message.answer(f"📧 *Emaillar ({i+1}/{len(chunks)} qism):*\n\n{chunk_text}")
                    await asyncio.sleep(0.5)  # Small delay between chunks
            else:
                await message.answer(f"📧 *Emaillar:*\n\n{format_emails_monospace(emails)}")
        
        if failed:
            failed_text = "❌ *Muvaffaqiyatsiz kalitlar:*\n\n"
            for i, key in enumerate(failed[:10], 1):
                failed_text += f"{i}. `{key}`\n"
            
            if len(failed) > 10:
                failed_text += f"\n... va yana {len(failed)-10} ta"
            
            await message.answer(failed_text)
        
        # Summary with statistics
        success_rate = len(emails) / len(keys) * 100 if keys else 0
        summary_text = (
            f"📊 *Natija*\n\n"
            f"✅ Muvaffaqiyatli: {len(emails)}\n"
            f"❌ Xatolik: {len(failed)}\n"
            f"📈 Muvaffaqiyat: {success_rate:.1f}%\n"
            f"⚡ Rejim: {mode_name}\n\n"
        )
        
        if is_admin(user_id):
            summary_text += "🔧 *Admin Panel*"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
                [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
                [InlineKeyboardButton(text="📩 Yana ishlatish", callback_data="use_bot")]
            ])
        else:
            summary_text += "📱 *Yana ishlatish uchun tugmalardan foydalaning*"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📩 10 daqiqa", callback_data="mode_10m")],
                [InlineKeyboardButton(text="📬 12 soat", callback_data="mode_12h")],
                [InlineKeyboardButton(text="📁 Fayl yuklash", callback_data="upload_file")]
            ])
        
        await message.answer(summary_text, reply_markup=keyboard)
        
    except Exception as e:
        print(f"Email processing error: {e}")
        await processing_msg.edit_text("❌ Email olishda xatolik yuz berdi! Qayta urinib ko'ring.")
    
    await state.set_state(Form.choosing_mode)

async def start_web_server():
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

async def main():
    print("🚀 Professional Bot ishga tushmoqda...")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"🌐 Port: {PORT}")
    
    # Setup connection pool for faster performance
    await setup_connection_pool()
    print("⚡ Connection pool initialized")
    
    # Start web server in background
    asyncio.create_task(start_web_server())
    
    # Start bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot to'xtatildi.")users_text) > 4000:
        parts = [users_text[i:i+4000] for i in range(0, len(users_text), 4000)]
        for part in parts:
            await callback.message.answer(part)
    else:
        await callback.message.answer(users_text)
    
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_statistics(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    stats = get_stats()
    
    # Calculate additional stats
    total_requests = sum(len(history) for history in user_history.values())
    total_emails = sum(
        sum(entry['emails_count'] for entry in history) 
        for history in user_history.values()
    )
    
    stats_text = (
        f"📊 *Bot Statistikasi*\n\n"
        f"👥 *Foydalanuvchilar:*\n"
        f"• Jami: {stats['total']}\n"
        f"• ✅ Tasdiqlangan: {stats['approved']}\n"
        f"• ⏳ Kutilayotgan: {stats['pending']}\n"
        f"• ❌ Rad etilgan: {stats['rejected']}\n\n"
        f"📈 *Faoliyat:*\n"
        f"• Jami so'rovlar: {total_requests}\n"
        f"• Jami emaillar: {total_emails}\n"
        f"• O'rtacha email/so'rov: {total_emails/max(total_requests,1):.1f}\n\n"
        f"🎫 *Support:*\n"
        f"• Ochiq tiketlar: {stats['active_tickets']}\n\n"
        f"⚙️ *Tizim:*\n"
        f"• Maintenance: {'🔴 ON' if maintenance_mode else '🟢 OFF'}\n"
        f"• Connection Pool: 🟢 Active\n"
        f"• Performance: ⚡ Optimized\n\n"
        f"📅 Hozirgi vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await callback.message.answer(stats_text)
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    await state.set_state(AdminStates.broadcast_message)
    await callback.message.answer(
        "📢 *Xabar yuborish*\n\n"
        "Barcha tasdiqlangan foydalanuvchilarga yuboriladi.\n\n"
        "Xabaringizni yozing:"
    )
    await callback.answer()

@dp.message(AdminStates.broadcast_message)
async def handle_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    broadcast_text = f"📢 *Admin xabari*\n\n{message.text}"
    
    # Show confirmation
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yuborish", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")]
    ])
    
    await state.update_data(broadcast_message=broadcast_text)
    await message.answer(
        f"📢 *Xabar ko'rinishi:*\n\n{broadcast_text}\n\n"
        f"📊 Yuboriladi: {get_stats()['approved']} ta foydalanuvchiga\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    data = await state.get_data()
    broadcast_text = data.get('broadcast_message')
    
    if not broadcast_text:
        await callback.message.answer("❌ Xabar topilmadi!")
        return
    
    processing_msg = await callback.message.answer("📤 Xabar yuborilmoqda...")
    
    sent_count, failed_count = await broadcast_message(broadcast_text, callback.from_user.id)
    
    await processing_msg.edit_text(
        f"📊 *Broadcast natijasi*\n\n"
        f"✅ Yuborildi: {sent_count}\n"
        f"❌ Xatolik: {failed_count}\n"
        f"📈 Muvaffaqiyat: {sent_count/(sent_count+failed_count)*100:.1f}%"
    )
    
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Broadcast bekor qilindi.")
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "admin_tickets")
async def admin_tickets_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    if not support_tickets:
        await callback.message.answer("🎫 Hozircha tiketlar yo'q.")
        await callback.answer()
        return
    
    tickets_text = "🎫 *Support tiketlar*\n\n"
    
    open_tickets = [t for t in support_tickets.values() if t['status'] == 'open']
    closed_tickets = [t for t in support_tickets.values() if t['status'] == 'closed']
    
    if open_tickets:
        tickets_text += "🟢 *Ochiq tiketlar:*\n"
        for ticket in open_tickets[-10:]:  # Last 10
            tickets_text += (
                f"• {ticket['user_name']} - {ticket['category']}\n"
                f"  `{ticket['id'][:20]}...` | {ticket['created_at']}\n\n"
            )
    
    if closed_tickets:
        tickets_text += f"\n✅ *Yopiq tiketlar:* {len(closed_tickets)} ta\n"
    
    await callback.message.answer(tickets_text)
    await callback.answer()

@dp.callback_query(F.data.startswith("reply_ticket_"))
async def reply_to_ticket(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    ticket_id = callback.data.replace("reply_ticket_", "")
    
    if ticket_id not in support_tickets:
        await callback.message.answer("❌ Tiket topilmadi!")
        return
    
    await state.update_data(replying_ticket_id=ticket_id)
    await state.set_state(AdminStates.replying_ticket)
    
    ticket = support_tickets[ticket_id]
    await callback.message.answer(
        f"💬 *Javob berish*\n\n"
        f"👤 Foydalanuvchi: {ticket['user_name']}\n"
        f"🆔 Tiket: `{ticket_id}`\n\n"
        "Javobingizni yozing:"
    )
    await callback.answer()

@dp.message(AdminStates.replying_ticket)
async def handle_ticket_reply(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data() 
    ticket_id = data.get('replying_ticket_id')
    
    if not ticket_id or ticket_id not in support_tickets:
        await message.answer("❌ Tiket topilmadi!")
        return
    
    ticket = support_tickets[ticket_id]
    user_id = ticket['user_id']
    
    # Send reply to user
    user_message = (
        f"💬 *Admin javobi*\n\n"
        f"🆔 Tiket: `{ticket_id}`\n"
        f"📅 Javob vaqti: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"💭 *Javob:*\n{message.text}"
    )
    
    try:
        await bot.send_message(user_id, user_message)
        
        # Close ticket
        support_tickets[ticket_id]['status'] = 'closed'
        support_tickets[ticket_id]['closed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        support_tickets[ticket_id]['admin_reply'] = message.text
        
        await message.answer(
            f"✅ *Javob yuborildi!*\n\n"
            f"👤 {ticket['user_name']} ga javob yuborildi.\n"
            f"🎫 Tiket avtomatik yopildi."
        )
        
    except Exception as e:
        print(f"Tiket javobida xatolik: {e}")
        await message.answer("❌ Javob yuborishda xatolik yuz berdi!")
    
    await state.clear()

@dp.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    ticket_id = callback.data.replace("close_ticket_", "")
    
    if ticket_id in support_tickets:
        support_tickets[ticket_id]['status'] = 'closed'
        support_tickets[ticket_id]['closed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        await callback.message.edit_text(
            f"✅ *Tiket yopildi*\n\n"
            f"🆔 ID: `{ticket_id}`\n"
            f"📅 Yopilgan: {support_tickets[ticket_id]['closed_at']}"
        )
    
    await callback.answer()

@dp.callback_query(F.data == "admin_settings")
async def admin_settings_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔧 Maintenance: {'🔴 ON' if maintenance_mode else '🟢 OFF'}", 
            callback_data="toggle_maintenance"
        )],
        [InlineKeyboardButton(text="📊 Export foydalanuvchilar", callback_data="export_users")],
        [InlineKeyboardButton(text="🗑️ Ma'lumotlarni tozalash", callback_data="cleanup_data")]
    ])
    
    await callback.message.answer(
        "⚙️ *Admin sozlamalari*\n\n"
        "Kerakli sozlamani tanlang:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance_mode(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    global maintenance_mode
    maintenance_mode = not maintenance_mode
    
    status_text = "🔴 YOQILDI" if maintenance_mode else "🟢 O'CHIRILDI"
    
    if maintenance_mode:
        # Notify all users about maintenance
        maintenance_message = (
            "🔧 *Bot yangilanmoqda*\n\n"
            "Vaqtincha bot ishlamaydi.\n"
            "Yangilanish tugagach xabar beramiz.\n\n"
            "Sabr qilib kutishingizni so'raymiz! 🙏"
        )
        
        sent, failed = await broadcast_message(maintenance_message, callback.from_user.id)
        
        await callback.message.edit_text(
            f"🔧 *Maintenance rejimi {status_text}*\n\n"
            f"📤 Xabar yuborildi: {sent} ta foydalanuvchiga\n"
            f"❌ Xatolik: {failed} ta"
        )
    else:
        # Notify users that bot is back online
        online_message = (
            "✅ *Bot yana ishlaydi!*\n\n"
            "Yangilanish tugadi.\n"
            "Botdan yana foydalanishingiz mumkin!\n\n"
            "/start ni bosing! 🚀"
        )
        
        sent, failed = await broadcast_message(online_message, callback.from_user.id)
        
        await callback.message.edit_text(
            f"✅ *Maintenance rejimi {status_text}*\n\n"
            f"📤 Xabar yuborildi: {sent} ta foydalanuvchiga\n"
            f"❌ Xatolik: {failed} ta"
        )
    
    await callback.answer()

# User features
@dp.callback_query(F.data == "my_stats")
async def user_statistics(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_approved_user(user_id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    user_data = users_db.get(str(user_id), {})
    history = user_history.get(str(user_id), [])
    
    total_requests = len(history)
    total_emails = sum(entry['emails_count'] for entry in history)
    
    # Mode statistics
    mode_10m = len([h for h in history if '10m' in h['mode']])
    mode_12h = len([h for h in history if '12h' in h['mode']])
    file_requests = len([h for h in history if 'file' in h['mode']])
    
    stats_text = (
        f"📊 *Sizning statistikangiz*\n\n"
        f"👤 *Profil:*\n"
        f"• Ism: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
        f"• Ro'yxat: {user_data.get('registered_at', 'N/A')}\n\n"
        f"📈 *Faoliyat:*\n"
        f"• Jami so'rovlar: {total_requests}\n"
        f"• Jami emaillar: {total_emails}\n"
        f"• O'rtacha: {total_emails/max(total_requests,1):.1f} email/so'rov\n\n"
        f"📋 *Rejimlar:*\n"
        f"• 📩 10 daqiqa: {mode_10m} marta\n"
        f"• 📬 12 soat: {mode_12h} marta\n"
        f"• 📁 Fayl yuklash: {file_requests} marta\n\n"
    )
    
    if history:
        stats_text += f"📅 *Oxirgi faoliyat:*\n{history[-1]['timestamp']}"
    
    await callback.message.answer(stats_text)
    await callback.answer()

@dp.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    help_text = (
        "❓ *Yordam*\n\n"
        "🤖 *Bot imkoniyatlari:*\n\n"
        "📩 *Email olish:*\n"
        "• 10 daqiqa - vaqtinchalik emaillar\n"
        "• 12 soat - uzoqroq emaillar\n"
        "• Kalitlarni matn yoki fayl ko'rinishida yuboring\n\n"
        "📁 *Fayl yuklash:*\n"
        "• .txt, .csv, .json formatlar\n"
        "• Maksimal 100 ta kalit\n"
        "• Maksimal fayl hajmi: 5MB\n\n"
        "🔧 *Boshqa funksiyalar:*\n"
        "• 📊 Statistika ko'rish\n"
        "• 📞 Admin bilan bog'lanish\n"
        "• 📈 Faoliyat tarixi\n\n"
        "⚡ *Tezkor maslahatlar:*\n"
        "• Fayl yuklash tezroq ishlaydi\n"
        "• Parallel processing ishlatiladi\n"
        "• Xatolik bo'lsa qayta urinib ko'ring\n\n"
        "📞 Savollar bo'lsa 'Admin bilan bog'lanish' tugmasini bosing!"
    )
    
    await callback.message.answer(help_text)
    await callback.answer()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    user_id = callback.data.split("_")[1]
    
    if user_id not in pending_users:
        await callback.answer("Foydalanuvchi topilmadi!")
        return
    
    user_data = pending_users[user_id]
    user_data['status'] = 'approved'
    user_data['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_user(int(user_id), user_data)
    del pending_users[user_id]
    
    try:
        welcome_message = (
            "🎉 *Tabriklaymiz!*\n\n"
            "Sizning so'rovingiz tasdiqlandi!\n\n"
            "🚀 *Endi botdan to'liq foydalanishingiz mumkin:*\n"
            "• 📩 Email olish (10 min / 12 soat)\n"
            "• 📁 Fayl yuklash (.txt, .csv, .json)\n"
            "• 📊 O'z statistikangizni ko'rish\n"
            "• 📞 Admin bilan bog'lanish\n"
            "• ❓ Yordam bo'limi\n\n"
            "Boshlash uchun: /start 🎯"
        )
        
        await bot.send_message(int(user_id), welcome_message)
    except Exception as e:
        print(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
    
    await callback.message.edit_text(
        f"✅ *Foydalanuvchi tasdiqlandi*\n\n"
        f"👨‍💼 {user_data['first_name']} {user_data['last_name']}\n"
        f"📱 {user_data['phone']}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📅 Tasdiqlangan: {user_data['approved_at']}"
    )
    await callback.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
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
    
    try:
        reject_message = (
            "❌ *So'rov rad etildi*\n\n"
            "Afsuski, sizning so'rovingiz rad etildi.\n\n"
            "🔄 *Qayta urinish:*\n"
            "Agar xatolik bo'lgan deb hisoblasangiz, "
            "/start buyrug'ini yuborib qayta so'rov qilishingiz mumkin.\n\n"
            "📞 Savollar bo'lsa admin bilan bog'laning."
        )
        
        await bot.send_message(int(user_id), reject_message)
    except Exception as e:
        print(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
    
    await callback.message.edit_text(
        f"❌ *Foydalanuvchi rad etildi*\n\n"
        f"👨‍💼 {user_data['first_name']} {user_data['last_name']}\n"
        f"📱 {user_data['phone']}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📅 Rad etilgan: {user_data['rejected_at']}"
    )
    await callback.answer("❌ Rad etildi!")

@dp.callback_query(F.data == "use_bot")
async def admin_use_bot(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 10 daqiqa pochta", callback_data="mode_10m")],
        [InlineKeyboardButton(text="📬 12 soat pochta", callback_data="mode_12h")],
        [InlineKeyboardButton(text="📁 Fayl yuklash", callback_data="upload_file")]
    ])

    await state.set_state(Form.choosing_mode)
    await callback.message.answer(
        "🔧 *Admin sifatida bot funksiyalari:*\n\n"
        "Barcha funksiyalardan foydalanishingiz mumkin:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("mode_"))
async def mode_selected(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id) and not is_approved_user(user_id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    mode = callback.data.replace("mode_", "")
    await state.update_data(mode=mode)
    await state.set_state(Form.waiting_keys)

    mode_name = "10 daqiqa" if mode == "10m" else "12 soat"
    
    await callback.message.answer(
        f"📝 *{mode_name} pochta*\n\n"
        "Kalitlar ro'yxatini yuboring:\n\n"
        "📋 *Formatlar:*\n"
        "• Har bir kalit yangi qatorda\n"
        "• `Key : kalit` formatida\n"
        "• Yoki 📁 fayl yuklang\n\n"
        "Kalitlaringizni yuboring:"
    )
    await callback.answer()

@dp.message(Form.waiting_keys)
async def handle_keys(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not is_admin(user_id) and not is_approved_user(user_id):
        await message.answer("❌ Sizda ruxsat yo'q!")
        return
    
    data = await state.get_data()
    mode = data.get("mode", "10m")
    minutes = 10 if mode == "10m" else 720
    base_url = BASE_URLS.get(mode, BASE_URLS["10m"])

    keys = extract_keys_from_text(message.text)
    if not keys:
        await message.answer(
            "❌ Kalitlar topilmadi!\n\n"
            "📋 *To'g'ri format:*\n"
            "• Har bir kalit yangi qatorda\n"
            "• `Key : kalit` formatida\n"
            "• Yoki 📁 fayl yuklang"
        )
        return
    
    if len(import sys
import os
import asyncio
import aiohttp
import json
import re
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Environment variables
API_TOKEN = os.environ.get('BOT_TOKEN', "8403878780:AAGebqROs5PhBejKf5alU4lBwL-JNG-0pWs")
PORT = int(os.environ.get('PORT', 8000))
ADMIN_ID = 976525232

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

# Enhanced in-memory database
users_db = {}
pending_users = {}
support_tickets = {}
user_history = {}
maintenance_mode = False

# Connection pool for faster email requests
connector = None

class Form(StatesGroup):
    choosing_mode = State()
    waiting_keys = State()
    waiting_contact = State()
    waiting_file = State()

class AdminStates(StatesGroup):
    viewing_stats = State()
    broadcast_message = State()
    replying_ticket = State()

class SupportStates(StatesGroup):
    waiting_message = State()
    waiting_category = State()

# Health check endpoint
async def health_check(request):
    return web.Response(text="Bot is running! ✅", status=200)

async def create_app():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    return app

async def setup_connection_pool():
    """Setup optimized connection pool for faster email requests"""
    global connector
    connector = aiohttp.TCPConnector(
        limit=100,
        limit_per_host=30,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
        ttl_dns_cache=300,
        use_dns_cache=True,
    )

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
    rejected_users = len([u for u in users_db.values() if u['status'] == 'rejected'])
    active_tickets = len([t for t in support_tickets.values() if t['status'] == 'open'])
    
    return {
        'total': total_users,
        'approved': approved_users,
        'pending': pending_users_count,
        'rejected': rejected_users,
        'active_tickets': active_tickets
    }

def extract_keys_from_text(text: str) -> list[str]:
    """Enhanced key extraction with multiple patterns"""
    keys = []
    
    # Pattern 1: Key : value
    pattern1 = re.findall(r'Key\s*:\s*(.+?)(?:\n|$)', text, re.IGNORECASE)
    keys.extend([k.strip() for k in pattern1])
    
    # Pattern 2: Simple lines (not URLs, not empty, not common words)
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if (line and 
            not line.startswith(('http', 'www', 'Key', 'Link')) and 
            len(line) > 5 and 
            not any(word in line.lower() for word in ['tool', 'email', 'password', 'login'])):
            keys.append(line)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keys = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique_keys.append(key)
    
    return unique_keys

def extract_keys_from_file_content(content: str, filename: str) -> list[str]:
    """Extract keys from uploaded file content"""
    keys = []
    
    try:
        if filename.endswith('.json'):
            # Try to parse as JSON
            data = json.loads(content)
            if isinstance(data, list):
                keys = [str(item) for item in data if str(item).strip()]
            elif isinstance(data, dict):
                # Look for common key patterns in JSON
                for key in ['keys', 'tokens', 'values', 'data']:
                    if key in data and isinstance(data[key], list):
                        keys = [str(item) for item in data[key] if str(item).strip()]
                        break
        
        elif filename.endswith('.csv'):
            # Parse CSV content
            lines = content.strip().split('\n')
            for line in lines[1:]:  # Skip header
                parts = line.split(',')
                if parts:
                    keys.append(parts[0].strip().strip('"'))
        
        else:
            # Treat as plain text
            keys = extract_keys_from_text(content)
    
    except Exception as e:
        print(f"Error parsing file {filename}: {e}")
        # Fallback to text parsing
        keys = extract_keys_from_text(content)
    
    return keys

def format_emails_monospace(emails: list[str]) -> str:
    lines = [f"{i+1} - `{email}`" for i, email in enumerate(emails)]
    lines.append(f"\n`AKA999aka`")
    return "\n".join(lines)

async def get_email_from_key_optimized(session: aiohttp.ClientSession, key: str, minutes: int, base_url: str) -> str | None:
    """Optimized email fetching with faster timeouts"""
    url = f"{base_url}?key_value={key}&timelive={minutes}"
    
    for attempt in range(3):  # Reduced from 5 to 3 attempts
        try:
            timeout = aiohttp.ClientTimeout(total=8)  # Reduced from 30 to 8 seconds
            async with session.get(url, timeout=timeout) as resp:
                text = await resp.text()
                print(f"API response for {key}: {text[:50]}...")
                if "@" in text:
                    email = text.strip().split("|")[0]
                    return email
        except Exception as e:
            print(f"[ERROR] attempt {attempt+1} for key {key}: {e}")
        
        if attempt < 2:  # Don't sleep after last attempt
            await asyncio.sleep(0.3)  # Reduced from 1 to 0.3 seconds
    
    return None

async def get_multiple_emails_parallel(keys: list[str], minutes: int, base_url: str) -> tuple[list[str], list[str]]:
    """Get emails in parallel for faster processing"""
    global connector
    
    if not connector:
        await setup_connection_pool()
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Create tasks for parallel execution
        tasks = [
            get_email_from_key_optimized(session, key, minutes, base_url)
            for key in keys
        ]
        
        # Execute all requests in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        emails = []
        failed = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append(keys[i])
            elif result:
                emails.append(result)
            else:
                failed.append(keys[i])
    
    return emails, failed

def save_user_history(user_id: int, keys_count: int, emails_count: int, mode: str):
    """Save user activity history"""
    if str(user_id) not in user_history:
        user_history[str(user_id)] = []
    
    user_history[str(user_id)].append({
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'keys_count': keys_count,
        'emails_count': emails_count,
        'mode': mode
    })
    
    # Keep only last 10 entries
    user_history[str(user_id)] = user_history[str(user_id)][-10:]

async def broadcast_message(message_text: str, exclude_user_id: int = None):
    """Send message to all approved users"""
    sent_count = 0
    failed_count = 0
    
    for user_id, user_data in users_db.items():
        if user_data['status'] == 'approved' and int(user_id) != exclude_user_id:
            try:
                await bot.send_message(int(user_id), message_text)
                sent_count += 1
                await asyncio.sleep(0.1)  # Avoid rate limiting
            except Exception as e:
                print(f"Failed to send broadcast to {user_id}: {e}")
                failed_count += 1
    
    return sent_count, failed_count

@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Maintenance mode check
    if maintenance_mode and not is_admin(user_id):
        await message.answer(
            "🔧 *Bot yangilanmoqda...*\n\n"
            "Iltimos, biroz kutib turing. "
            "Yangilanish tugagach xabar beramiz.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    # Admin uchun
    if is_admin(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="🎫 Support tikеtlar", callback_data="admin_tickets")],
            [InlineKeyboardButton(text="🔧 Sozlamalar", callback_data="admin_settings")],
            [InlineKeyboardButton(text="📩 Botdan foydalanish", callback_data="use_bot")]
        ])
        await message.answer(
            "🔧 *Admin Panel*\n\n"
            f"Salom admin! Bot holatini boshqaring.\n"
            f"Maintenance: {'🔴 ON' if maintenance_mode else '🟢 OFF'}",
            reply_markup=keyboard
        )
        return
    
    # Tasdiqlangan foydalanuvchi uchun
    if is_approved_user(user_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 10 daqiqa pochta", callback_data="mode_10m")],
            [InlineKeyboardButton(text="📬 12 soat pochta", callback_data="mode_12h")],
            [InlineKeyboardButton(text="📁 Fayl yuklash", callback_data="upload_file")],
            [InlineKeyboardButton(text="📞 Admin bilan bog'lanish", callback_data="contact_admin")],
            [InlineKeyboardButton(text="📊 Mening statistikam", callback_data="my_stats")],
            [InlineKeyboardButton(text="❓ Yordam", callback_data="help")]
        ])

        await state.set_state(Form.choosing_mode)
        await message.answer(
            "✅ *Xush kelibsiz!*\n\n"
            "Siz tasdiqlangan foydalanuvchisiz. Kerakli variantni tanlang:",
            reply_markup=keyboard
        )
        return
    
    # Yangi foydalanuvchi yoki kutilayotgan
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
            "📋 *Ro'yxatdan o'tish jarayoni:*\n"
            "1. Kontaktingizni ulashing\n"
            "2. Admin tasdiqlashini kuting\n"
            "3. Botdan foydalanishni boshlang\n\n"
            "Davom etish uchun kontaktingizni ulashing 👇",
            reply_markup=contact_keyboard
        )
    else:
        user_status = users_db[str(user_id)]['status']
        if user_status == 'rejected':
            # Rejected user can re-request
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Qayta so'rov yuborish", callback_data="re_request")]
            ])
            await message.answer(
                "❌ *So'rovingiz rad etilgan*\n\n"
                "Agar xatolik bo'lgan deb hisoblasangiz, "
                "qayta so'rov yuborishingiz mumkin.",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                "⏳ *Kutilmoqda...*\n\n"
                "Sizning so'rovingiz admin tomonidan ko'rib chiqilmoqda.\n"
                "Tasdiqlangandan keyin xabar olasiz."
            )

@dp.callback_query(F.data == "re_request")
async def handle_re_request(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if str(user_id) in users_db:
        # Move from rejected to pending
        user_data = users_db[str(user_id)]
        user_data['status'] = 'pending'
        user_data['re_requested_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pending_users[str(user_id)] = user_data
        
        # Notify admin
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user_id}")
            ]
        ])
        
        admin_message = (
            f"🔄 *Qayta so'rov*\n\n"
            f"👨‍💼 Ism: {user_data['first_name']} {user_data['last_name']}\n"
            f"🆔 Username: @{user_data['username']}\n"
            f"📱 Telefon: {user_data['phone']}\n"
            f"🆔 ID: `{user_id}`\n"
            f"📅 Birinchi so'rov: {user_data['registered_at']}\n"
            f"🔄 Qayta so'rov: {user_data['re_requested_at']}\n\n"
            f"⚠️ Bu foydalanuvchi avval rad etilgan edi."
        )
        
        try:
            await bot.send_message(ADMIN_ID, admin_message, reply_markup=admin_keyboard)
            await callback.message.edit_text(
                "✅ *Qayta so'rov yuborildi!*\n\n"
                "Admin ko'rib chiqadi va javob beradi."
            )
        except Exception as e:
            print(f"Admin'ga qayta so'rov yuborishda xatolik: {e}")
            await callback.message.edit_text("❌ Xatolik yuz berdi. Qayta urinib ko'ring.")
    
    await callback.answer()

@dp.message(Form.waiting_contact, F.contact)
async def handle_contact(message: Message, state: FSMContext):
    user_id = message.from_user.id
    contact = message.contact
    
    print(f"Contact received from user {user_id}")
    
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
    print(f"User {user_id} added to pending users")
    
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
        print(f"Admin message sent for user {user_id}")
        await message.answer(
            "✅ *So'rov yuborildi!*\n\n"
            "📋 *Keyingi qadamlar:*\n"
            "• Sizning ma'lumotlaringiz admin'ga yuborildi\n"
            "• Admin ko'rib chiqadi (odatda 24 soat ichida)\n"
            "• Tasdiqlangandan keyin xabar olasiz\n"
            "• Keyin botdan to'liq foydalanishingiz mumkin",
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        print(f"Admin'ga xabar yuborishda xatolik: {e}")
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    await state.clear()

# File upload handler
@dp.callback_query(F.data == "upload_file")
async def upload_file_request(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_approved_user(user_id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    await state.set_state(Form.waiting_file)
    await callback.message.answer(
        "📁 *Fayl yuklash*\n\n"
        "Quyidagi formatdagi fayllarni yuklashingiz mumkin:\n\n"
        "📄 *.txt* - har bir kalit yangi qatorda\n"
        "📊 *.csv* - CSV format (birinchi ustun kalitlar)\n"
        "🔧 *.json* - JSON format\n\n"
        "Faylni yuboring:"
    )
    await callback.answer()

@dp.message(Form.waiting_file, F.document)
async def handle_file_upload(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not is_approved_user(user_id):
        await message.answer("❌ Sizda ruxsat yo'q!")
        return
    
    document = message.document
    
    # Check file size (max 5MB)
    if document.file_size > 5 * 1024 * 1024:
        await message.answer("❌ Fayl hajmi 5MB dan kichik bo'lishi kerak!")
        return
    
    # Check file extension
    filename = document.file_name.lower()
    allowed_extensions = ['.txt', '.csv', '.json']
    
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        await message.answer(
            "❌ Faqat quyidagi formatlar qabul qilinadi:\n"
            "• .txt\n• .csv\n• .json"
        )
        return
    
    try:
        # Download file
        file_info = await bot.get_file(document.file_id)
        file_content = await bot.download_file(file_info.file_path)
        
        # Read content
        content = file_content.read().decode('utf-8')
        
        # Extract keys
        keys = extract_keys_from_file_content(content, filename)
        
        if not keys:
            await message.answer("❌ Faylda kalitlar topilmadi!")
            return
        
        if len(keys) > 100:
            await message.answer(f"❌ Maksimal 100 ta kalit. Sizda {len(keys)} ta.")
            return
        
        # Ask for mode selection
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 10 daqiqa", callback_data="file_mode_10m")],
            [InlineKeyboardButton(text="📬 12 soat", callback_data="file_mode_12h")]
        ])
        
        await state.update_data(file_keys=keys)
        await message.answer(
            f"✅ *Fayl muvaffaqiyatli yuklandi!*\n\n"
            f"📊 Topilgan kalitlar: {len(keys)}\n"
            f"📁 Fayl nomi: {document.file_name}\n\n"
            "Pochta turini tanlang:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        print(f"File processing error: {e}")
        await message.answer("❌ Faylni qayta ishlashda xatolik yuz berdi!")

@dp.callback_query(F.data.startswith("file_mode_"))
async def handle_file_mode(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_approved_user(user_id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    data = await state.get_data()
    keys = data.get('file_keys', [])
    
    if not keys:
        await callback.message.answer("❌ Kalitlar topilmadi. Qayta urinib ko'ring.")
        return
    
    mode = callback.data.replace("file_mode_", "")
    minutes = 10 if mode == "10m" else 720
    base_url = BASE_URLS.get(mode, BASE_URLS["10m"])
    
    # Processing message
    processing_msg = await callback.message.answer(
        f"⚡ *Email olish jarayoni boshlanmoqda...*\n\n"
        f"📊 Kalitlar soni: {len(keys)}\n"
        f"🚀 Tez rejim: Parallel processing\n"
        f"⏱️ Taxminiy vaqt: {len(keys) * 0.5:.1f} sekund\n\n"
        f"Iltimos kuting..."
    )
    
    try:
        # Use optimized parallel processing
        emails, failed = await get_multiple_emails_parallel(keys, minutes, base_url)
        
        # Save to history
        save_user_history(user_id, len(keys), len(emails), f"file_{mode}")
        
        if emails:
            await callback.message.answer(format_emails_monospace(emails))
        
        if failed:
            await callback.message.answer(
                f"❌ Muvaffaqiyatsiz ({len(failed)} ta):\n" + 
                "\n".join([f"• `{key}`" for key in failed[:10]]) +
                (f"\n... va yana {len(failed)-10} ta" if len(failed) > 10 else "")
            )
        
        # Summary
        await callback.message.answer(
            f"📊 *Natija*\n\n"
            f"✅ Muvaffaqiyatli: {len(emails)}\n"
            f"❌ Muvaffaqiyatsiz: {len(failed)}\n"
            f"📊 Jami: {len(keys)}\n"
            f"📈 Muvaffaqiyat darajasi: {len(emails)/len(keys)*100:.1f}%"
        )
        
        # Delete processing message
        await processing_msg.delete()
        
    except Exception as e:
        print(f"File email processing error: {e}")
        await callback.message.answer("❌ Email olishda xatolik yuz berdi!")
    
    await state.clear()
    await callback.answer()

# Support system
@dp.callback_query(F.data == "contact_admin")
async def contact_admin_menu(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_approved_user(user_id):
        await callback.answer("Sizda ruxsat yo'q!")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐛 Texnik muammo", callback_data="support_bug")],
        [InlineKeyboardButton(text="❓ Savol", callback_data="support_question")],
        [InlineKeyboardButton(text="💡 Taklif", callback_data="support_suggestion")],
        [InlineKeyboardButton(text="💬 Boshqa", callback_data="support_other")]
    ])
    
    await callback.message.answer(
        "📞 *Admin bilan bog'lanish*\n\n"
        "Muammo turini tanlang:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("support_"))
async def handle_support_category(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    category = callback.data.replace("support_", "")
    
    category_names = {
        'bug': '🐛 Texnik muammo',
        'question': '❓ Savol', 
        'suggestion': '💡 Taklif',
        'other': '💬 Boshqa'
    }
    
    await state.update_data(support_category=category)
    await state.set_state(SupportStates.waiting_message)
    
    await callback.message.answer(
        f"📝 *{category_names.get(category, 'Xabar')}*\n\n"
        "Xabaringizni yozing. Shuningdek, rasm yoki fayl yuborishingiz ham mumkin:"
    )
    await callback.answer()

@dp.message(SupportStates.waiting_message)
async def handle_support_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    category = data.get('support_category', 'other')
    
    # Create ticket
    ticket_id = f"{user_id}_{int(datetime.now().timestamp())}"
    
    user_data = users_db.get(str(user_id), {})
    
    ticket_data = {
        'id': ticket_id,
        'user_id': user_id,
        'category': category,
        'message': message.text or "Media fayl",
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'open',
        'user_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
    }
    
    support_tickets[ticket_id] = ticket_data

# Send to admin
category_names = {
    'bug': '🐛 Texnik muammo',
    'question': '❓ Savol',
    'suggestion': '💡 Taklif', 
    'other': '💬 Boshqa'
}

admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_ticket_{ticket_id}")],
    [InlineKeyboardButton(text="✅ Yopish", callback_data=f"close_ticket_{ticket_id}")]
])

admin_message = (
    f"🎫 *Yangi support tiket*\n\n"
    f"👤 Foydalanuvchi: {ticket_data['user_name']}\n"
    f"🆔 ID: `{user_id}`\n"
    f"📋 Kategoriya: {category_names.get(category, 'Noma\'lum')}\n"
    f"📅 Vaqt: {ticket_data['created_at']}\n"
    f"🆔 Tiket ID: `{ticket_id}`\n\n"
    f"💬 *Xabar:*\n{message.text or 'Media fayl yuborilgan'}"
)

try:
    # Forward message to admin
    if message.text:
        await bot.send_message(ADMIN_ID, admin_message, reply_markup=admin_keyboard)
    else:
        # Forward media
        await message.forward(ADMIN_ID)
        await bot.send_message(ADMIN_ID, admin_message, reply_markup=admin_keyboard)
    
    await message.answer(
        f"✅ *Xabaringiz yuborildi!*\n\n"
        f"🆔 Tiket ID: `{ticket_id}`\n"
        f"📋 Kategoriya: {category_names.get(category)}\n"
        f"⏱️ Admin odatda 24 soat ichida javob beradi.\n\n"
        f"Javob kelganda sizga xabar beramiz."
    )
    
except Exception as e:
    print(f"Support ticket yuborishda xatolik: {e}")
    await message.answer("❌ Xatolik yuz berdi. Qayta urinib ko'ring.")

await state.clear()
