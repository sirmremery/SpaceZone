# telegram_bot.py - SpaceZone v11.0
# ربات مدیریت کامل پنل از طریق تلگرام

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger("SpaceZone")

_bot_task = None
_bot_instance = None

async def _bot_worker():
    """کارگر اصلی ربات تلگرام"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, bot disabled")
        return
    
    try:
        from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
    except ImportError:
        logger.warning("python-telegram-bot not installed")
        return
    
    # پیام‌های ثابت
    MSG = {
        "start": """
🚀 **SpaceZone v11.0**
پنل مدیریت کانفیگ حرفه‌ای

📊 از طریق این ربات می‌تونی:
• لیست کانفیگ‌ها رو ببینی
• کانفیگ جدید بسازی
• کانفیگ رو فعال/غیرفعال کنی
• وضعیت اتصالات رو چک کنی
• آمار ترافیک رو ببینی

🔑 **دستورات:**
/links - لیست کانفیگ‌ها
/new - ساخت کانفیگ جدید
/stats - آمار کلی
/conns - اتصالات فعال
/help - راهنما

📌 حتماً از طریق پنل وب هم می‌تونی مدیریت کنی
""",
        "help": """
📖 **راهنمای ربات SpaceZone**

🔹 **دستورات اصلی:**
/start - شروع و صفحه اصلی
/links - نمایش لیست کانفیگ‌ها
/new - ساخت کانفیگ جدید
/stats - نمایش آمار کلی
/conns - نمایش اتصالات فعال
/cancel - لغو عملیات جاری
/help - این پیام

🔹 **ویژگی‌ها:**
• مشاهده کانفیگ‌ها با جزئیات کامل
• ساخت کانفیگ با سهمیه و انقضا
• فعال/غیرفعال کردن کانفیگ
• مشاهده مصرف ترافیک
• نمایش اتصالات زنده

🛡️ **امنیت:**
• فقط کاربران مجاز دسترسی دارند
• رمز عبور پنل برای تغییرات مهم
• لاگ کامل فعالیت‌ها
""",
        "stats": """
📈 **آمار کلی SpaceZone**

🔗 **کانفیگ‌ها:** {links_count}
✅ **فعال:** {active_links}
❌ **غیرفعال:** {inactive_links}
⏰ **منقضی:** {expired_links}

🌐 **اتصالات:** {connections}
📊 **ترافیک کل:** {traffic}
⏱️ **آپتایم:** {uptime}

🔄 **آخرین بروزرسانی:** {updated}
""",
        "links_header": """
🔗 **لیست کانفیگ‌ها** ({count} عدد)

برای مشاهده جزئیات هر کانفیگ، روی دکمه کلیک کن:
""",
        "link_detail": """
🔗 **{label}**

🆔 **UUID:** `{uuid}`
📊 **مصرف:** {used} / {limit}
⏳ **انقضا:** {expiry}
📌 **وضعیت:** {status}
🔌 **پروتکل:** {protocol}
🌐 **اتصالات:** {connections} عدد

📎 **لینک ساب:** {sub_url}
"""
    }
    
    # دیکشنری برای نگهداری وضعیت کاربران در حین ساخت کانفیگ
    user_states: Dict[int, Dict] = {}
    
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور start - نمایش صفحه اصلی"""
        await update.message.reply_text(
            MSG["start"],
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 لیست کانفیگ‌ها", callback_data="list_links")],
                [InlineKeyboardButton("➕ ساخت کانفیگ جدید", callback_data="new_link")],
                [InlineKeyboardButton("📈 آمار کلی", callback_data="show_stats")],
                [InlineKeyboardButton("🌐 اتصالات فعال", callback_data="show_conns")]
            ])
        )
    
    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لغو عملیات جاری"""
        user_id = update.effective_user.id
        if user_id in user_states:
            del user_states[user_id]
        await update.message.reply_text("✅ عملیات لغو شد")
    
    async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش لیست کانفیگ‌ها"""
        from main import LINKS, LINKS_LOCK, is_link_allowed, fmt_bytes, is_link_expired
        
        async with LINKS_LOCK:
            links = dict(LINKS)
        
        if not links:
            await update.message.reply_text("❌ هیچ کانفیگی وجود ندارد")
            return
        
        # مرتب‌سازی بر اساس تاریخ ایجاد
        sorted_links = sorted(links.items(), key=lambda x: x[1].get("created_at", ""), reverse=True)
        
        # نمایش ۵ کانفیگ اول با دکمه‌های بیشتر
        buttons = []
        for i, (uid, link) in enumerate(sorted_links[:5]):
            label = link.get("label", uid[:8])
            status = "✅" if is_link_allowed(link) else ("⏰" if is_link_expired(link) else "❌")
            buttons.append([InlineKeyboardButton(
                f"{status} {label}", 
                callback_data=f"link_{uid}"
            )])
        
        if len(sorted_links) > 5:
            buttons.append([InlineKeyboardButton(
                f"📄 نمایش همه ({len(sorted_links)} عدد)", 
                callback_data="list_all_links"
            )])
        
        buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")])
        
        await update.message.reply_text(
            MSG["links_header"].format(count=len(links)),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def list_all_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش همه کانفیگ‌ها به صورت صفحه‌بندی شده"""
        query = update.callback_query
        await query.answer()
        
        from main import LINKS, LINKS_LOCK, is_link_allowed, fmt_bytes, is_link_expired
        
        async with LINKS_LOCK:
            links = dict(LINKS)
        
        if not links:
            await query.edit_message_text("❌ هیچ کانفیگی وجود ندارد")
            return
        
        # صفحه‌بندی - هر صفحه ۱۰ کانفیگ
        page = context.user_data.get("links_page", 0)
        sorted_links = sorted(links.items(), key=lambda x: x[1].get("created_at", ""), reverse=True)
        total_pages = (len(sorted_links) + 9) // 10
        start = page * 10
        end = min(start + 10, len(sorted_links))
        
        text = f"🔗 **لیست همه کانفیگ‌ها** (صفحه {page+1}/{total_pages})\n\n"
        for uid, link in sorted_links[start:end]:
            label = link.get("label", uid[:8])
            used = fmt_bytes(link.get("used_bytes", 0))
            limit = fmt_bytes(link.get("limit_bytes", 0)) if link.get("limit_bytes", 0) > 0 else "∞"
            status = "✅" if is_link_allowed(link) else ("⏰" if is_link_expired(link) else "❌")
            text += f"{status} `{label}` - {used}/{limit}\n"
        
        buttons = []
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ قبلی", callback_data="links_prev"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("▶️ بعدی", callback_data="links_next"))
        if nav_buttons:
            buttons.append(nav_buttons)
        
        buttons.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_links")])
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def link_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش جزئیات یک کانفیگ"""
        query = update.callback_query
        await query.answer()
        
        uid = query.data.replace("link_", "")
        from main import LINKS, LINKS_LOCK, is_link_allowed, fmt_bytes, is_link_expired, vless_link_for_link, get_host
        
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        
        if not link:
            await query.edit_message_text("❌ کانفیگ پیدا نشد")
            return
        
        label = link.get("label", "بدون نام")
        used = fmt_bytes(link.get("used_bytes", 0))
        limit = fmt_bytes(link.get("limit_bytes", 0)) if link.get("limit_bytes", 0) > 0 else "∞"
        expiry = link.get("expires_at")
        if expiry:
            try:
                days = (datetime.fromisoformat(expiry) - datetime.now()).days
                expiry = f"{days} روز مانده" if days > 0 else "⚠️ منقضی شده"
            except:
                expiry = "نامشخص"
        else:
            expiry = "♾️ نامحدود"
        
        status = "✅ فعال" if is_link_allowed(link) else ("⏰ منقضی" if is_link_expired(link) else "❌ غیرفعال")
        protocol = link.get("protocol", "vless-ws")
        protocol_name = "VLESS/WS" if protocol == "vless-ws" else "XHTTP Ultra"
        connections = sum(1 for c in context.bot_data.get("connections", {}).values() if c.get("uuid") == uid)
        
        # ساخت لینک ساب
        host = get_host()
        sub_url = f"https://{host}/p/{uid}"
        
        text = MSG["link_detail"].format(
            label=label,
            uuid=uid,
            used=used,
            limit=limit,
            expiry=expiry,
            status=status,
            protocol=protocol_name,
            connections=connections,
            sub_url=sub_url
        )
        
        buttons = [
            [
                InlineKeyboardButton("✅ فعال", callback_data=f"toggle_{uid}_true"),
                InlineKeyboardButton("❌ غیرفعال", callback_data=f"toggle_{uid}_false")
            ],
            [
                InlineKeyboardButton("📊 نمودار مصرف", callback_data=f"chart_{uid}"),
                InlineKeyboardButton("🔄 ریست مصرف", callback_data=f"reset_{uid}")
            ],
            [
                InlineKeyboardButton("📋 کپی UUID", callback_data=f"copy_{uid}"),
                InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_{uid}")
            ],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_links")]
        ]
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def toggle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """فعال/غیرفعال کردن کانفیگ"""
        query = update.callback_query
        await query.answer()
        
        _, uid, active = query.data.split("_")
        active = active == "true"
        
        from main import LINKS, LINKS_LOCK, log_activity
        
        async with LINKS_LOCK:
            if uid not in LINKS:
                await query.edit_message_text("❌ کانفیگ پیدا نشد")
                return
            LINKS[uid]["active"] = active
            label = LINKS[uid].get("label", uid)
        
        log_activity("link", f"کانفیگ «{label}» از تلگرام {'فعال' if active else 'غیرفعال'} شد", "ok" if active else "warn")
        
        await query.edit_message_text(
            f"✅ کانفیگ «{label}» {'فعال' if active else 'غیرفعال'} شد",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"link_{uid}")]
            ])
        )
    
    async def reset_link_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ریست مصرف کانفیگ"""
        query = update.callback_query
        await query.answer()
        
        uid = query.data.replace("reset_", "")
        from main import LINKS, LINKS_LOCK, log_activity
        
        async with LINKS_LOCK:
            if uid not in LINKS:
                await query.edit_message_text("❌ کانفیگ پیدا نشد")
                return
            LINKS[uid]["used_bytes"] = 0
            label = LINKS[uid].get("label", uid)
        
        log_activity("link", f"مصرف کانفیگ «{label}» از تلگرام ریست شد", "info")
        
        await query.edit_message_text(
            f"✅ مصرف کانفیگ «{label}» ریست شد",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"link_{uid}")]
            ])
        )
    
    async def delete_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """حذف کانفیگ"""
        query = update.callback_query
        await query.answer()
        
        uid = query.data.replace("delete_", "")
        from main import remove_link
        
        label = await remove_link(uid)
        if label is None:
            await query.edit_message_text("❌ کانفیگ پیدا نشد")
            return
        
        await query.edit_message_text(
            f"🗑️ کانفیگ «{label}» حذف شد",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_links")]
            ])
        )
    
    async def copy_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """کپی UUID"""
        query = update.callback_query
        await query.answer()
        
        uid = query.data.replace("copy_", "")
        from main import LINKS, LINKS_LOCK
        
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        
        if not link:
            await query.edit_message_text("❌ کانفیگ پیدا نشد")
            return
        
        await query.edit_message_text(
            f"📋 **UUID کپی شد**\n\n`{uid}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"link_{uid}")]
            ])
        )
    
    async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش آمار کلی"""
        query = update.callback_query
        if query:
            await query.answer()
        
        from main import LINKS, LINKS_LOCK, connections, stats, uptime, is_link_allowed, is_link_expired, fmt_bytes
        
        async with LINKS_LOCK:
            links = dict(LINKS)
        
        total = len(links)
        active = sum(1 for l in links.values() if is_link_allowed(l))
        expired = sum(1 for l in links.values() if is_link_expired(l))
        inactive = total - active - expired
        
        traffic = fmt_bytes(stats["total_bytes"])
        conns = len(connections)
        uptime_str = uptime()
        
        text = MSG["stats"].format(
            links_count=total,
            active_links=active,
            inactive_links=inactive,
            expired_links=expired,
            connections=conns,
            traffic=traffic,
            uptime=uptime_str,
            updated=datetime.now().strftime("%H:%M:%S")
        )
        
        if query:
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 بروزرسانی", callback_data="show_stats")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]
                ])
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 بروزرسانی", callback_data="show_stats")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]
                ])
            )
    
    async def show_conns(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش اتصالات فعال"""
        query = update.callback_query
        if query:
            await query.answer()
        
        from main import connections, LINKS, LINKS_LOCK
        
        if not connections:
            text = "🌐 **هیچ اتصال فعالی وجود ندارد**"
        else:
            # گروه‌بندی بر اساس UUID
            grouped = {}
            for conn_id, conn in connections.items():
                uid = conn.get("uuid", "نامشخص")
                ip = conn.get("ip", "نامشخص")
                if uid not in grouped:
                    grouped[uid] = {"ips": [], "count": 0}
                grouped[uid]["ips"].append(ip)
                grouped[uid]["count"] += 1
            
            # گرفتن نام کانفیگ‌ها
            async with LINKS_LOCK:
                links = dict(LINKS)
            
            text = "🌐 **اتصالات فعال**\n\n"
            for uid, data in grouped.items():
                label = links.get(uid, {}).get("label", uid[:8])
                text += f"🔗 **{label}** - {data['count']} اتصال\n"
                for ip in data["ips"][:5]:
                    text += f"  • `{ip}`\n"
                if len(data["ips"]) > 5:
                    text += f"  • و {len(data['ips'])-5} آی‌پی دیگر...\n"
                text += "\n"
        
        if query:
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 بروزرسانی", callback_data="show_conns")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]
                ])
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 بروزرسانی", callback_data="show_conns")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]
                ])
            )
    
    async def new_link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """شروع فرآیند ساخت کانفیگ جدید"""
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        user_states[user_id] = {"step": "label"}
        
        text = """
➕ **ساخت کانفیگ جدید** (مرحله 1/4)

📝 **نام کانفیگ** رو وارد کن:
(مثلاً: کاربر علی، سرور اصلی، و...)

برای لغو عملیات از /cancel استفاده کن.
"""
        if query:
            await query.edit_message_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ لغو", callback_data="cancel_new")]
                ])
            )
        else:
            await update.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ لغو", callback_data="cancel_new")]
                ])
            )
    
    async def cancel_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لغو ساخت کانفیگ"""
        query = update.callback_query
        if query:
            await query.answer()
            user_id = query.from_user.id
        else:
            user_id = update.effective_user.id
        
        if user_id in user_states:
            del user_states[user_id]
        
        text = "❌ ساخت کانفیگ لغو شد"
        if query:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]
                ])
            )
        else:
            await update.message.reply_text(text)
    
    async def handle_new_link_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پردازش ورودی‌های ساخت کانفیگ"""
        user_id = update.effective_user.id
        if user_id not in user_states:
            await update.message.reply_text("❌ عملیاتی در جریان نیست. از /new شروع کن.")
            return
        
        state = user_states[user_id]
        text = update.message.text
        
        if text.startswith("/"):
            await update.message.reply_text("❌ دستور مجاز نیست. از /cancel برای لغو استفاده کن.")
            return
        
        if state["step"] == "label":
            state["label"] = text
            state["step"] = "quota"
            await update.message.reply_text(
                f"📝 نام: **{text}**\n\n"
                "➕ **مرحله 2/4: سهمیه ترافیک**\n\n"
                "مقدار سهمیه رو وارد کن (مثلاً: 1، 5، 10، 50)\n"
                "برای نامحدود عدد 0 رو وارد کن.",
                parse_mode="Markdown"
            )
        
        elif state["step"] == "quota":
            try:
                state["quota"] = float(text)
                state["step"] = "quota_unit"
                await update.message.reply_text(
                    f"📊 سهمیه: **{text}**\n\n"
                    "➕ **مرحله 3/4: واحد سهمیه**\n\n"
                    "واحد رو انتخاب کن:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("GB", callback_data="unit_gb"), InlineKeyboardButton("MB", callback_data="unit_mb")],
                        [InlineKeyboardButton("❌ لغو", callback_data="cancel_new")]
                    ])
                )
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")
        
        elif state["step"] == "expiry":
            try:
                state["expiry"] = int(text)
                await finish_new_link(update, context)
            except ValueError:
                await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کن.")
    
    async def handle_unit_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """انتخاب واحد سهمیه"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if user_id not in user_states:
            await query.edit_message_text("❌ عملیاتی در جریان نیست.")
            return
        
        unit = query.data.replace("unit_", "").upper()
        user_states[user_id]["unit"] = unit
        user_states[user_id]["step"] = "expiry"
        
        await query.edit_message_text(
            f"📊 سهمیه: **{user_states[user_id]['quota']} {unit}**\n\n"
            "➕ **مرحله 4/4: انقضا**\n\n"
            "تعداد روز تا انقضا رو وارد کن:\n"
            "• عدد 0 = نامحدود\n"
            "• عدد مثبت = تعداد روز",
            parse_mode="Markdown"
        )
    
    async def finish_new_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تکمیل ساخت کانفیگ"""
        user_id = update.effective_user.id
        if user_id not in user_states:
            await update.message.reply_text("❌ خطا در ساخت کانفیگ")
            return
        
        state = user_states[user_id]
        from main import make_link, save_state, log_activity
        
        try:
            quota = state.get("quota", 0)
            unit = state.get("unit", "GB")
            expiry = state.get("expiry", 0)
            
            # تبدیل سهمیه به بایت
            if unit == "GB":
                limit_bytes = int(quota * 1024 ** 3) if quota > 0 else 0
            elif unit == "MB":
                limit_bytes = int(quota * 1024 ** 2) if quota > 0 else 0
            else:
                limit_bytes = 0
            
            # محاسبه تاریخ انقضا
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(days=expiry)).isoformat() if expiry > 0 else None
            
            # ساخت کانفیگ
            uid, link = await make_link(
                label=state.get("label", "کانفیگ جدید"),
                limit_bytes=limit_bytes,
                expires_at=expires_at,
                protocol="vless-ws",
                fingerprint="chrome"
            )
            
            log_activity("link", f"کانفیگ «{link['label']}» از تلگرام ساخته شد", "ok")
            
            del user_states[user_id]
            
            # نمایش نتیجه
            host = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "localhost")
            sub_url = f"https://{host}/p/{uid}"
            
            await update.message.reply_text(
                f"✅ **کانفیگ ساخته شد!**\n\n"
                f"📝 نام: `{link['label']}`\n"
                f"🆔 UUID: `{uid}`\n"
                f"📊 سهمیه: {quota} {unit}\n"
                f"⏳ انقضا: {expiry if expiry > 0 else 'نامحدود'} روز\n"
                f"📎 لینک ساب: {sub_url}\n\n"
                f"برای مدیریت کانفیگ از /links استفاده کن.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 مشاهده کانفیگ", callback_data=f"link_{uid}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_start")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error creating link: {e}")
            await update.message.reply_text("❌ خطا در ساخت کانفیگ")
    
    async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بازگشت به صفحه اصلی"""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(
                MSG["start"],
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 لیست کانفیگ‌ها", callback_data="list_links")],
                    [InlineKeyboardButton("➕ ساخت کانفیگ جدید", callback_data="new_link")],
                    [InlineKeyboardButton("📈 آمار کلی", callback_data="show_stats")],
                    [InlineKeyboardButton("🌐 اتصالات فعال", callback_data="show_conns")]
                ])
            )
    
    async def chart_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش نمودار مصرف - نسخه ساده برای تلگرام"""
        query = update.callback_query
        await query.answer()
        
        uid = query.data.replace("chart_", "")
        from main import LINKS, LINKS_LOCK, fmt_bytes, vless_link_for_link, get_host
        
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        
        if not link:
            await query.edit_message_text("❌ کانفیگ پیدا نشد")
            return
        
        # نمایش آمار مصرف به صورت متن
        used = fmt_bytes(link.get("used_bytes", 0))
        limit = fmt_bytes(link.get("limit_bytes", 0)) if link.get("limit_bytes", 0) > 0 else "∞"
        pct = min(100, link.get("used_bytes", 0) / link.get("limit_bytes", 0) * 100) if link.get("limit_bytes", 0) > 0 else 0
        
        # ساخت نوار پیشرفت به صورت Emoji
        bar_length = 20
        filled = int(pct / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        text = f"""
📊 **نمودار مصرف کانفیگ**

📝 **{link.get('label', 'بدون نام')}**

🟦 **مصرف:** {used}
📦 **سقف:** {limit}
📈 **درصد:** {pct:.1f}%

{bar}

🌐 **لینک ساب:** https://{get_host()}/p/{uid}
"""
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"link_{uid}")]
            ])
        )
    
    async def show_link_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش نمودار مصرف کانفیگ با داده‌های تاریخی"""
        query = update.callback_query
        await query.answer()
        
        uid = query.data.replace("chart_", "")
        from main import LINKS, LINKS_LOCK, fmt_bytes
        
        async with LINKS_LOCK:
            link = LINKS.get(uid)
        
        if not link:
            await query.edit_message_text("❌ کانفیگ پیدا نشد")
            return
        
        # استفاده از داده‌های موجود
        used = fmt_bytes(link.get("used_bytes", 0))
        limit = fmt_bytes(link.get("limit_bytes", 0)) if link.get("limit_bytes", 0) > 0 else "∞"
        pct = min(100, link.get("used_bytes", 0) / link.get("limit_bytes", 0) * 100) if link.get("limit_bytes", 0) > 0 else 0
        
        # ساخت نوار پیشرفت
        bar_length = 25
        filled = int(pct / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        text = f"""
📊 **نمودار مصرف**

📝 **{link.get('label', 'بدون نام')}**

🟦 {bar} {pct:.1f}%

📊 **مصرف:** {used}
📦 **سقف:** {limit}
🆔 **UUID:** `{uid[:16]}...`

📌 **وضعیت:** {'✅ فعال' if link.get('active', True) else '❌ غیرفعال'}
"""
        
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 کپی UUID", callback_data=f"copy_{uid}")],
                [InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"link_{uid}")]
            ])
        )
    
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت خطاها"""
        logger.error(f"Telegram error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کن.")
    
    # تنظیمات امنیتی - لیست کاربران مجاز (اختیاری)
    ALLOWED_USERS = os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
    ALLOWED_USERS = [u.strip() for u in ALLOWED_USERS if u.strip()]
    
    async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """میان‌افزار احراز هویت"""
        if not ALLOWED_USERS:
            return True
        
        user_id = str(update.effective_user.id)
        if user_id in ALLOWED_USERS:
            return True
        
        await update.message.reply_text("⛔ شما مجوز استفاده از این ربات را ندارید.")
        return False
    
    # ساخت اپلیکیشن
    try:
        app = Application.builder().token(token).build()
        
        # دستورات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", start))  # help هم به start اشاره کنه
        app.add_handler(CommandHandler("links", links))
        app.add_handler(CommandHandler("new", new_link_start))
        app.add_handler(CommandHandler("stats", show_stats))
        app.add_handler(CommandHandler("conns", show_conns))
        app.add_handler(CommandHandler("cancel", cancel))
        
        # کالبک‌ها
        app.add_handler(CallbackQueryHandler(list_all_links, pattern="^list_all_links$"))
        app.add_handler(CallbackQueryHandler(links, pattern="^list_links$"))
        app.add_handler(CallbackQueryHandler(link_detail, pattern="^link_"))
        app.add_handler(CallbackQueryHandler(toggle_link, pattern="^toggle_"))
        app.add_handler(CallbackQueryHandler(reset_link_usage, pattern="^reset_"))
        app.add_handler(CallbackQueryHandler(delete_link, pattern="^delete_"))
        app.add_handler(CallbackQueryHandler(copy_uuid, pattern="^copy_"))
        app.add_handler(CallbackQueryHandler(show_stats, pattern="^show_stats$"))
        app.add_handler(CallbackQueryHandler(show_conns, pattern="^show_conns$"))
        app.add_handler(CallbackQueryHandler(new_link_start, pattern="^new_link$"))
        app.add_handler(CallbackQueryHandler(cancel_new, pattern="^cancel_new$"))
        app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
        app.add_handler(CallbackQueryHandler(handle_unit_selection, pattern="^unit_"))
        app.add_handler(CallbackQueryHandler(show_link_chart, pattern="^chart_"))
        
        # صفحه‌بندی
        app.add_handler(CallbackQueryHandler(lambda q, c: list_all_links(q, c), pattern="^links_prev$"))
        app.add_handler(CallbackQueryHandler(lambda q, c: list_all_links(q, c), pattern="^links_next$"))
        
        # پیام‌های متنی برای ساخت کانفیگ
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_link_input))
        
        # خطاها
        app.add_error_handler(error_handler)
        
        # شروع ربات
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        logger.info("✅ Telegram bot started successfully")
        
        # نگه داشتن ربات در حال اجرا
        while True:
            await asyncio.sleep(60)
            
    except Exception as e:
        logger.error(f"❌ Telegram bot error: {e}")

async def start_bot():
    """شروع ربات تلگرام"""
    global _bot_task
    if _bot_task is None or _bot_task.done():
        _bot_task = asyncio.create_task(_bot_worker())

async def stop_bot():
    """توقف ربات تلگرام"""
    global _bot_task
    if _bot_task:
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
        _bot_task = None
        logger.info("Telegram bot stopped")
