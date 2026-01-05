"""
Birthday Organizer Bot - FastAPI Backend
Telegram-first micro-SaaS for team birthday gift collections
"""
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot.handlers import start_command, handle_callback, handle_message, help_command, handle_new_chat_members, handle_group_message, join_command
from bot.scheduler import setup_scheduler, stop_scheduler
from services.database import db_service

# Setup
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Telegram Bot setup
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.warning("TELEGRAM_TOKEN not set - bot functionality disabled")

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Telegram Application (global for webhook handling)
telegram_app = None
bot = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global telegram_app, bot
    
    if TELEGRAM_TOKEN:
        # Initialize Telegram bot
        telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
        bot = telegram_app.bot
        
        # Add handlers
        telegram_app.add_handler(CommandHandler("start", start_command))
        telegram_app.add_handler(CommandHandler("help", help_command))
        telegram_app.add_handler(CommandHandler("join", join_command))
        telegram_app.add_handler(CallbackQueryHandler(handle_callback))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))
        telegram_app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP), handle_group_message))
        
        # Initialize the application
        await telegram_app.initialize()
        await telegram_app.start()
        
        # Set up webhook
        webhook_url = os.environ.get('WEBHOOK_URL')
        if webhook_url:
            await bot.set_webhook(url=f"{webhook_url}/api/telegram/webhook")
            logger.info(f"Webhook set to: {webhook_url}/api/telegram/webhook")
        else:
            # Use polling for development
            logger.info("Starting bot in polling mode (no WEBHOOK_URL set)")
            await telegram_app.updater.start_polling(drop_pending_updates=True)
        
        # Setup scheduler
        setup_scheduler(bot)
        
        logger.info("Birthday Organizer Bot started successfully!")
    
    yield
    
    # Cleanup
    if telegram_app:
        stop_scheduler()
        await telegram_app.stop()
        await telegram_app.shutdown()
    
    client.close()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Birthday Organizer Bot",
    description="Telegram bot for coordinating team birthday gift collections",
    version="1.0.0",
    lifespan=lifespan
)

# Create API router
api_router = APIRouter(prefix="/api")


# Pydantic models for API
class HealthResponse(BaseModel):
    status: str
    bot_active: bool
    timestamp: str


class StatsResponse(BaseModel):
    total_users: int
    total_teams: int
    active_events: int
    completed_events: int


# API Routes
@api_router.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Birthday Organizer Bot API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@api_router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        bot_active=bool(TELEGRAM_TOKEN and bot),
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@api_router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get basic statistics"""
    users_count = await db.users.count_documents({})
    teams_count = await db.teams.count_documents({})
    active_events = await db.birthday_events.count_documents({"status": {"$ne": "completed"}})
    completed_events = await db.birthday_events.count_documents({"status": "completed"})
    
    return StatsResponse(
        total_users=users_count,
        total_teams=teams_count,
        active_events=active_events,
        completed_events=completed_events
    )


@api_router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Telegram webhook endpoint"""
    if not telegram_app:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/telegram/set-webhook")
async def set_webhook(webhook_url: str):
    """Manually set webhook URL"""
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        await bot.set_webhook(url=f"{webhook_url}/api/telegram/webhook")
        return {"status": "success", "webhook_url": f"{webhook_url}/api/telegram/webhook"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/telegram/webhook-info")
async def get_webhook_info():
    """Get current webhook info"""
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        info = await bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Manual trigger endpoints (for testing)
@api_router.post("/trigger/check-birthdays")
async def trigger_birthday_check():
    """Manually trigger birthday check"""
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    from bot.scheduler import check_upcoming_birthdays
    await check_upcoming_birthdays(bot)
    return {"status": "Birthday check triggered"}


@api_router.post("/trigger/send-greetings")
async def trigger_greetings():
    """Manually trigger birthday greetings"""
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    from bot.scheduler import send_birthday_greetings
    await send_birthday_greetings(bot)
    return {"status": "Birthday greetings triggered"}


@api_router.post("/trigger/3-day-reminders")
async def trigger_3_day_reminders():
    """Manually trigger 3-day reminders"""
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    from bot.scheduler import send_3_day_reminders
    await send_3_day_reminders(bot)
    return {"status": "3-day reminders triggered"}


@api_router.post("/trigger/1-day-reminders")
async def trigger_1_day_reminders():
    """Manually trigger 1-day reminders"""
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    from bot.scheduler import send_1_day_reminders
    await send_1_day_reminders(bot)
    return {"status": "1-day reminders triggered"}


@api_router.post("/trigger/all-scheduler-jobs")
async def trigger_all_jobs():
    """Manually trigger all scheduler jobs (for testing)"""
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    from bot.scheduler import (
        check_upcoming_birthdays, 
        send_birthday_greetings,
        send_3_day_reminders,
        send_1_day_reminders,
        send_organizer_reminders
    )
    
    results = {}
    
    try:
        await check_upcoming_birthdays(bot)
        results['check_birthdays'] = 'success'
    except Exception as e:
        results['check_birthdays'] = f'error: {str(e)}'
    
    try:
        await send_birthday_greetings(bot)
        results['send_greetings'] = 'success'
    except Exception as e:
        results['send_greetings'] = f'error: {str(e)}'
    
    try:
        await send_3_day_reminders(bot)
        results['3_day_reminders'] = 'success'
    except Exception as e:
        results['3_day_reminders'] = f'error: {str(e)}'
    
    try:
        await send_1_day_reminders(bot)
        results['1_day_reminders'] = 'success'
    except Exception as e:
        results['1_day_reminders'] = f'error: {str(e)}'
    
    try:
        await send_organizer_reminders(bot)
        results['organizer_reminders'] = 'success'
    except Exception as e:
        results['organizer_reminders'] = f'error: {str(e)}'
    
    return {"status": "All jobs triggered", "results": results}


# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
