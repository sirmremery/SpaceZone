# telegram_bot.py - SpaceZone v11.0 (اختیاری)

import os
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("SpaceZone")

_bot_task = None

async def _bot_worker():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    try:
        from telegram import Bot, Update
        from telegram.ext import Application, CommandHandler, ContextTypes
    except ImportError:
        logger.warning("python-telegram-bot not installed")
        return

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🚀 SpaceZone v11.0\nپنل مدیریت کانفیگ")

    async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from main import LINKS, LINKS_LOCK
        async with LINKS_LOCK:
            count = len(LINKS)
            active = sum(1 for l in LINKS.values() if l.get("active", True))
        await update.message.reply_text(f"📊 وضعیت کانفیگ‌ها:\nکل: {count}\nفعال: {active}")

    async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from main import connections, stats
        await update.message.reply_text(
            f"📈 آمار:\n"
            f"اتصالات: {len(connections)}\n"
            f"ترافیک کل: {stats['total_bytes']/1024**2:.1f} MB\n"
            f"آپتایم: {stats.get('uptime', '—')}"
        )

    try:
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("links", links))
        app.add_handler(CommandHandler("stats", stats))
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Telegram bot started")
        while True:
            await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")

async def start_bot():
    global _bot_task
    if _bot_task is None or _bot_task.done():
        _bot_task = asyncio.create_task(_bot_worker())

async def stop_bot():
    global _bot_task
    if _bot_task:
        _bot_task.cancel()
        try:
            await _bot_task
        except:
            pass
        _bot_task = None
