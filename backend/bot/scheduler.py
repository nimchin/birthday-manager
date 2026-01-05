"""
Scheduler for Birthday Organizer Bot
Handles automated reminders and birthday announcements
"""
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
import os

from services.database import db_service
from models.schemas import BirthdayEvent, EventStatus
from bot.keyboards import event_invitation_keyboard

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def get_display_name(user_data: dict) -> str:
    """Get display name - prefer @username, fallback to first_name"""
    username = user_data.get('username')
    if username:
        return f"@{username}"
    return user_data.get('first_name', 'User')


async def check_upcoming_birthdays(bot: Bot):
    """Check for birthdays 2 weeks away and create events with private invitations"""
    logger.info("Checking for upcoming birthdays...")
    
    target_date = datetime.now(timezone.utc) + timedelta(days=14)
    target_mmdd = target_date.strftime("%m-%d")
    birthday_full = target_date.strftime("%Y-%m-%d")
    
    # Get all teams
    teams = await db_service.get_all_teams()
    
    for team in teams:
        team_id = team.get('telegram_chat_id')
        team_name = team.get('title', 'your team')
        
        # Get team members with birthday on target date
        users = await db_service.get_users_by_team(team_id)
        
        for user in users:
            if user.get('date_of_birth') != target_mmdd:
                continue
            
            user_id = user.get('telegram_id')
            user_name = get_display_name(user)
            
            # Check if event already exists
            existing = await db_service.get_event_by_person_and_date(
                user_id, birthday_full, team_id
            )
            
            if existing:
                continue
            
            # Create new birthday event
            event = BirthdayEvent(
                birthday_person_id=user_id,
                birthday_person_name=user_name,
                team_id=team_id,
                birthday_date=birthday_full,
                status=EventStatus.VOTING,
                wishlist_snapshot=user.get('wishlist', []),
                voting_started_at=datetime.now(timezone.utc)
            )
            
            await db_service.create_event(event.model_dump())
            logger.info(f"Created birthday event for {user_name} on {birthday_full}")
            
            # Build wishlist text
            wishlist_text = ""
            if user.get('wishlist'):
                wishlist_text = "\n\n<b>Wishlist:</b>\n"
                for item in user.get('wishlist', [])[:5]:
                    title = item.get('title', 'Item')
                    url = item.get('url', '')
                    if url:
                        wishlist_text += f"• <a href='{url}'>{title}</a>\n"
                    else:
                        wishlist_text += f"• {title}\n"
            
            # Send PRIVATE invitations to all team members (except birthday person)
            for member in users:
                member_id = member.get('telegram_id')
                if member_id == user_id:
                    continue
                
                try:
                    await bot.send_message(
                        chat_id=member_id,
                        text=(
                            f"🎂 <b>Birthday Coming Up!</b>\n\n"
                            f"<b>{user_name}</b>'s birthday is on <b>{birthday_full}</b> (14 days away)\n"
                            f"Team: {team_name}"
                            f"{wishlist_text}\n\n"
                            f"Would you like to participate in the gift collection?"
                        ),
                        parse_mode="HTML",
                        reply_markup=event_invitation_keyboard(event.id),
                        disable_web_page_preview=True
                    )
                    logger.info(f"Sent birthday invitation to {member_id}")
                except Exception as e:
                    logger.debug(f"Could not notify member {member_id}: {e}")


async def send_3_day_reminders(bot: Bot):
    """Send reminders 3 days before birthday"""
    logger.info("Sending 3-day reminders...")
    
    events = await db_service.get_events_needing_reminders(3)
    
    for event in events:
        event_id = event.get('id')
        pending_contributions = await db_service.get_pending_contributions(event_id)
        
        for contribution in pending_contributions:
            user_id = contribution.get('user_id')
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"⏰ <b>Reminder!</b>\n\n"
                        f"{event.get('birthday_person_name')}'s birthday is in 3 days!\n\n"
                        f"Don't forget to:\n"
                        f"• Vote for a gift\n"
                        f"• Mark your contribution as paid\n"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Could not send reminder to {user_id}: {e}")


async def send_1_day_reminders(bot: Bot):
    """Send reminders 1 day before birthday"""
    logger.info("Sending 1-day reminders...")
    
    events = await db_service.get_events_needing_reminders(1)
    
    for event in events:
        event_id = event.get('id')
        pending_contributions = await db_service.get_pending_contributions(event_id)
        
        for contribution in pending_contributions:
            user_id = contribution.get('user_id')
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🚨 <b>Last Day Reminder!</b>\n\n"
                        f"{event.get('birthday_person_name')}'s birthday is TOMORROW!\n\n"
                        f"Please mark your contribution as paid if you haven't already!"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Could not send reminder to {user_id}: {e}")


async def send_organizer_reminders(bot: Bot):
    """Send reminders to organizers if gift not ordered 7 days after finalization"""
    logger.info("Checking organizer reminders...")
    
    events = await db_service.get_events_by_status("finalized")
    
    for event in events:
        finalized_at = event.get('finalized_at')
        if not finalized_at:
            continue
        
        if isinstance(finalized_at, str):
            finalized_at = datetime.fromisoformat(finalized_at)
        
        days_since = (datetime.now(timezone.utc) - finalized_at).days
        
        if days_since >= 7:
            organizer_id = event.get('organizer_id')
            if organizer_id:
                try:
                    await bot.send_message(
                        chat_id=organizer_id,
                        text=(
                            f"📦 <b>Organizer Reminder!</b>\n\n"
                            f"It's been {days_since} days since you finalized the gift for "
                            f"{event.get('birthday_person_name')}'s birthday.\n\n"
                            f"Don't forget to order the gift!"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.debug(f"Could not send organizer reminder to {organizer_id}: {e}")


async def send_birthday_greetings(bot: Bot):
    """Send birthday greetings on the day"""
    logger.info("Checking for today's birthdays...")
    
    events = await db_service.get_todays_birthdays()
    
    greetings = [
        "🎂🎉 <b>HAPPY BIRTHDAY</b> 🎉🎂",
        "🎈🎁 <b>Happy Birthday!</b> 🎁🎈",
        "🥳🎂 <b>Birthday Time!</b> 🎂🥳",
    ]
    
    import random
    
    for event in events:
        team_id = event.get('team_id')
        birthday_person = event.get('birthday_person_name')
        birthday_person_id = event.get('birthday_person_id')
        
        try:
            greeting = random.choice(greetings)
            await bot.send_message(
                chat_id=team_id,
                text=(
                    f"{greeting}\n\n"
                    f"Today we celebrate {birthday_person}! 🎊\n\n"
                    f"Wishing you an amazing day filled with joy and happiness! 🌟"
                ),
                parse_mode="HTML"
            )
            
            # Update event status
            await db_service.update_event(event.get('id'), {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc)
            })
            
            logger.info(f"Sent birthday greeting for {birthday_person}")
            
        except Exception as e:
            logger.error(f"Failed to send greeting to team {team_id}: {e}")


def setup_scheduler(bot: Bot):
    """Set up all scheduled jobs"""
    # Check upcoming birthdays daily at 9 AM
    scheduler.add_job(
        check_upcoming_birthdays,
        CronTrigger(hour=9, minute=0),
        args=[bot],
        id="check_birthdays",
        replace_existing=True
    )
    
    # 3-day reminders at 10 AM
    scheduler.add_job(
        send_3_day_reminders,
        CronTrigger(hour=10, minute=0),
        args=[bot],
        id="3_day_reminders",
        replace_existing=True
    )
    
    # 1-day reminders at 10 AM
    scheduler.add_job(
        send_1_day_reminders,
        CronTrigger(hour=18, minute=40),
        args=[bot],
        id="1_day_reminders",
        replace_existing=True
    )
    
    # Organizer reminders at 11 AM
    scheduler.add_job(
        send_organizer_reminders,
        CronTrigger(hour=11, minute=0),
        args=[bot],
        id="organizer_reminders",
        replace_existing=True
    )
    
    # Birthday greetings at 9 AM
    scheduler.add_job(
        send_birthday_greetings,
        CronTrigger(hour=18, minute=40),
        args=[bot],
        id="birthday_greetings",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started with all jobs")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("Scheduler stopped")
