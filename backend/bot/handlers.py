"""
Telegram Bot Handlers for Birthday Organizer Bot
"""
import logging
from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.constants import ChatType
from datetime import datetime, timezone, timedelta
import uuid

from services.database import db_service
from models.schemas import User, Team, BirthdayEvent, Contribution, WishlistItem, ContributionStatus, EventStatus
from bot.keyboards import (
    main_menu_keyboard, join_collection_keyboard, event_actions_keyboard,
    wishlist_keyboard, wishlist_manage_keyboard, wishlist_remove_keyboard,
    events_list_keyboard, back_to_menu_keyboard, month_keyboard, day_keyboard,
    finalize_options_keyboard, confirm_keyboard
)

logger = logging.getLogger(__name__)

# Conversation states storage (simple in-memory for MVP)
user_states = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - different behavior for groups vs private"""
    chat_type = update.effective_chat.type
    user = update.effective_user
    
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        # Bot added to group - register team
        await handle_group_start(update, context)
    else:
        # Private chat - user onboarding
        await handle_private_start(update, context)


async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /join command - register user with the team (silent in group)"""
    chat_type = update.effective_chat.type
    
    if chat_type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text(
            "Use this command in a group chat to join the team!"
        )
        return
    
    chat = update.effective_chat
    user = update.effective_user
    
    # Make sure team exists
    existing_team = await db_service.get_team(chat.id)
    if not existing_team:
        team = Team(
            telegram_chat_id=chat.id,
            title=chat.title or "Unknown Team"
        )
        await db_service.create_team(team.model_dump())
        logger.info(f"New team registered via /join: {chat.title} ({chat.id})")
    
    # Check if user exists in bot
    existing_user = await db_service.get_user(user.id)
    if not existing_user:
        # Create user
        new_user = User(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        await db_service.create_user(new_user.model_dump())
        existing_user = new_user.model_dump()
    
    # Add to team
    await db_service.add_user_to_team(user.id, chat.id)
    await db_service.add_member_to_team(chat.id, user.id)
    
    # Send private message to user (not in group)
    try:
        if existing_user.get('date_of_birth') and existing_user.get('onboarded'):
            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    f"✅ You've joined the team *{chat.title}*!\n\n"
                    "You'll receive private notifications about upcoming birthdays in this team."
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
            # Check for immediate birthdays and send invitations
            await check_and_send_birthday_invitations_for_new_member(user.id, chat.id, context.bot)
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    f"✅ You've joined the team *{chat.title}*!\n\n"
                    "Please set your birthday so your team can celebrate you!"
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
    except Exception as e:
        logger.debug(f"Could not send private message to {user.id}: {e}")
    
    # Delete the /join command message to keep group clean
    try:
        await update.message.delete()
    except Exception as e:
        logger.debug(f"Could not delete /join message: {e}")


async def handle_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bot being added to a group - silent registration"""
    chat = update.effective_chat
    
    # Check if team exists
    existing_team = await db_service.get_team(chat.id)
    if not existing_team:
        team = Team(
            telegram_chat_id=chat.id,
            title=chat.title or "Unknown Team"
        )
        await db_service.create_team(team.model_dump())
        logger.info(f"New team registered: {chat.title} ({chat.id})")
    
    # Register the user who added the bot to this team
    user = update.effective_user
    if user:
        existing_user = await db_service.get_user(user.id)
        if existing_user:
            await db_service.add_user_to_team(user.id, chat.id)
            await db_service.add_member_to_team(chat.id, user.id)
        
        # Send instructions privately to the user who added the bot
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    f"🎂 *Birthday Organizer Bot* added to *{chat.title}*!\n\n"
                    "The bot will only post birthday greetings in the group.\n\n"
                    "*How to set up your team:*\n"
                    "1️⃣ Ask all team members to type `/join` in the group\n"
                    "2️⃣ Each member sets their birthday here (privately)\n"
                    "3️⃣ Everyone gets private notifications about upcoming birthdays\n\n"
                    "Use the menu below to set your birthday!"
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            logger.debug(f"Could not send private instructions to {user.id}: {e}")


async def handle_private_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private chat start - user onboarding"""
    user = update.effective_user
    
    # Check if user exists
    existing_user = await db_service.get_user(user.id)
    
    if not existing_user:
        # Create new user
        new_user = User(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        await db_service.create_user(new_user.model_dump())
        
        await update.message.reply_text(
            f"👋 Welcome, {user.first_name}!\n\n"
            "I'm the *Birthday Organizer Bot*. I help teams coordinate birthday gift collections.\n\n"
            "Let's get you set up:\n"
            "1️⃣ Set your birthday date\n"
            "2️⃣ Add items to your wishlist (optional)\n"
            "3️⃣ Add me to your team's group chat\n\n"
            "Use the menu below to get started!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            f"👋 Welcome back, {user.first_name}!\n\n"
            "What would you like to do?",
            reply_markup=main_menu_keyboard()
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback query handler"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    logger.info(f"Callback: {data} from user {user_id}")
    
    # Route to appropriate handler
    if data == "main_menu":
        await show_main_menu(query)
    elif data == "set_birthday":
        await show_birthday_month_selection(query)
    elif data.startswith("month_"):
        await show_birthday_day_selection(query, data)
    elif data.startswith("day_"):
        await handle_birthday_day_selection(query, data)
    elif data == "view_wishlist":
        await show_wishlist(query)
    elif data == "add_wishlist_item":
        await prompt_wishlist_add(query)
    elif data == "remove_wishlist_item":
        await show_wishlist_remove(query)
    elif data.startswith("delwish_"):
        await handle_wishlist_delete(query, data)
    elif data == "my_events":
        await show_my_events(query)
    elif data.startswith("event_"):
        await show_event_details(query, data)
    elif data.startswith("accept_"):
        await handle_accept_invitation(query, data)
    elif data.startswith("skip_"):
        await handle_skip_invitation(query, data)
    elif data.startswith("join_"):
        await handle_join_event(query, data)
    elif data.startswith("contribute_"):
        await handle_contribute(query, data)
    elif data.startswith("vote_"):
        await show_voting_options(query, data)
    elif data.startswith("vw_"):
        await handle_vote(query, data)
    elif data.startswith("ev_"):
        await handle_short_event_back(query, data)
    elif data.startswith("discuss_"):
        await handle_discussion_request(query, data)
    elif data.startswith("organize_"):
        await handle_become_organizer(query, data)
    elif data.startswith("finalize_"):
        await show_finalize_options(query, data)
    elif data.startswith("sg_"):
        await handle_gift_selection(query, data)
    elif data.startswith("cg_"):
        await prompt_custom_gift(query, data)
    elif data.startswith("stepdown_"):
        await handle_organizer_stepdown(query, data)
    elif data.startswith("decline_"):
        await handle_decline_participation(query, data)
    elif data.startswith("view_contrib_"):
        await show_contributions_summary(query, data)
    elif data == "help":
        await show_help(query)


async def show_main_menu(query):
    """Show main menu"""
    await query.edit_message_text(
        "🎂 *Birthday Organizer Bot*\n\nWhat would you like to do?",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


async def show_birthday_month_selection(query):
    """Show month selection for birthday"""
    await query.edit_message_text(
        "📅 *Set Your Birthday*\n\nSelect your birth month:",
        parse_mode="Markdown",
        reply_markup=month_keyboard()
    )


async def show_birthday_day_selection(query, data):
    """Show day selection for birthday"""
    month = data.split("_")[1]
    month_names = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December"
    }
    await query.edit_message_text(
        f"📅 *Set Your Birthday*\n\nMonth: {month_names.get(month, month)}\nSelect your birth day:",
        parse_mode="Markdown",
        reply_markup=day_keyboard(month)
    )


async def handle_birthday_day_selection(query, data):
    """Handle birthday day selection and save"""
    parts = data.split("_")
    month = parts[1]
    day = parts[2]
    user_id = query.from_user.id
    
    date_of_birth = f"{month}-{day}"
    
    await db_service.update_user(user_id, {
        "date_of_birth": date_of_birth,
        "onboarded": True
    })
    
    month_names = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December"
    }
    
    await query.edit_message_text(
        f"✅ *Birthday Set!*\n\n"
        f"Your birthday: {month_names.get(month)} {int(day)}\n\n"
        "Now add items to your wishlist so your team knows what to get you!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    
    # Check if birthday is within next 14 days and trigger immediate event creation
    await check_and_create_immediate_event(user_id, date_of_birth, query.get_bot())


async def check_and_create_immediate_event(user_id: int, date_of_birth: str, bot):
    """Check if user's birthday is within 14 days and create event with private invitations"""
    from bot.keyboards import event_invitation_keyboard
    
    today = datetime.now(timezone.utc)
    current_year = today.year
    
    # Parse MM-DD format
    month, day = date_of_birth.split("-")
    
    # Calculate birthday date for this year
    birthday_this_year = datetime(current_year, int(month), int(day), tzinfo=timezone.utc)
    
    # If birthday already passed this year, check next year
    if birthday_this_year.date() < today.date():
        birthday_this_year = datetime(current_year + 1, int(month), int(day), tzinfo=timezone.utc)
    
    days_until = (birthday_this_year.date() - today.date()).days
    
    # If birthday is within 14 days, create events for all teams
    if 0 < days_until <= 14:
        logger.info(f"Birthday for user {user_id} is in {days_until} days - creating immediate events")
        
        user = await db_service.get_user(user_id)
        if not user:
            return
        
        user_name = user.get('first_name', 'Team member')
        birthday_full = birthday_this_year.strftime("%Y-%m-%d")
        
        # Create events for each team the user belongs to
        for team_id in user.get('teams', []):
            # Check if event already exists
            existing = await db_service.get_event_by_person_and_date(
                user_id, birthday_full, team_id
            )
            
            if existing:
                continue
            
            # Get team info
            team = await db_service.get_team(team_id)
            team_name = team.get('title', 'your team') if team else 'your team'
            
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
            logger.info(f"Created birthday event for {user_name} on {birthday_full} in team {team_id}")
            
            # Send PRIVATE invitations to all team members (except birthday person)
            team_users = await db_service.get_users_by_team(team_id)
            for member in team_users:
                member_id = member.get('telegram_id')
                if member_id == user_id:
                    continue
                
                try:
                    wishlist_text = ""
                    if user.get('wishlist'):
                        wishlist_text = "\n\n*Wishlist:*\n"
                        for item in user.get('wishlist', [])[:5]:
                            title = item.get('title', 'Item')
                            url = item.get('url', '')
                            if url:
                                wishlist_text += f"• [{title}]({url})\n"
                            else:
                                wishlist_text += f"• {title}\n"
                    
                    await bot.send_message(
                        chat_id=member_id,
                        text=(
                            f"🎂 *Birthday Coming Up!*\n\n"
                            f"*{user_name}*'s birthday is on *{birthday_full}* ({days_until} days away)\n"
                            f"Team: {team_name}"
                            f"{wishlist_text}\n\n"
                            f"Would you like to participate in the gift collection?"
                        ),
                        parse_mode="Markdown",
                        reply_markup=event_invitation_keyboard(event.id),
                        disable_web_page_preview=True
                    )
                    logger.info(f"Sent birthday invitation to {member_id} for event {event.id}")
                except Exception as e:
                    logger.debug(f"Could not send invitation to {member_id}: {e}")


async def check_and_send_birthday_invitations_for_new_member(user_id: int, team_id: int, bot):
    """Send pending birthday invitations to a newly joined team member"""
    from bot.keyboards import event_invitation_keyboard
    
    today = datetime.now(timezone.utc)
    
    # Get all active events for this team
    events = await db_service.get_events_by_status("voting")
    
    for event in events:
        if event.get('team_id') != team_id:
            continue
        
        # Don't invite the birthday person
        if event.get('birthday_person_id') == user_id:
            continue
        
        # Check if user already participated
        if user_id in event.get('participants', []):
            continue
        
        # Check if already has a contribution record
        existing_contribution = await db_service.get_contribution(event.get('id'), user_id)
        if existing_contribution:
            continue
        
        # Get team info
        team = await db_service.get_team(team_id)
        team_name = team.get('title', 'your team') if team else 'your team'
        
        # Calculate days until
        birthday_date = datetime.strptime(event.get('birthday_date'), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_until = (birthday_date.date() - today.date()).days
        
        if days_until <= 0:
            continue
        
        # Get birthday person's wishlist
        birthday_person = await db_service.get_user(event.get('birthday_person_id'))
        wishlist_text = ""
        if birthday_person and birthday_person.get('wishlist'):
            wishlist_text = "\n\n*Wishlist:*\n"
            for item in birthday_person.get('wishlist', [])[:5]:
                title = item.get('title', 'Item')
                url = item.get('url', '')
                if url:
                    wishlist_text += f"• [{title}]({url})\n"
                else:
                    wishlist_text += f"• {title}\n"
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎂 *Birthday Coming Up!*\n\n"
                    f"*{event.get('birthday_person_name')}*'s birthday is on *{event.get('birthday_date')}* ({days_until} days away)\n"
                    f"Team: {team_name}"
                    f"{wishlist_text}\n\n"
                    f"Would you like to participate in the gift collection?"
                ),
                parse_mode="Markdown",
                reply_markup=event_invitation_keyboard(event.get('id')),
                disable_web_page_preview=True
            )
            logger.info(f"Sent pending birthday invitation to new member {user_id}")
        except Exception as e:
            logger.debug(f"Could not send invitation to {user_id}: {e}")


async def show_wishlist(query):
    """Show user's wishlist"""
    user_id = query.from_user.id
    user = await db_service.get_user(user_id)
    
    if not user:
        await query.edit_message_text("Please use /start first.")
        return
    
    wishlist = user.get('wishlist', [])
    
    if not wishlist:
        text = "🎁 *Your Wishlist*\n\nYour wishlist is empty. Add items so your team knows what to get you!"
    else:
        text = "🎁 *Your Wishlist*\n\n"
        for i, item in enumerate(wishlist, 1):
            title = item.get('title', 'Unknown')
            url = item.get('url', '')
            if url:
                text += f"{i}. [{title}]({url})\n"
            else:
                text += f"{i}. {title}\n"
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=wishlist_manage_keyboard(),
        disable_web_page_preview=True
    )


async def prompt_wishlist_add(query):
    """Prompt user to add wishlist item"""
    user_id = query.from_user.id
    user_states[user_id] = {"state": "awaiting_wishlist_item"}
    
    await query.edit_message_text(
        "🎁 *Add Wishlist Item*\n\n"
        "Send me the item you want to add.\n\n"
        "Format: `Item name` or `Item name | URL`\n\n"
        "Example:\n"
        "• `AirPods Pro`\n"
        "• `Sony Headphones | https://amazon.com/...`",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def show_wishlist_remove(query):
    """Show wishlist items for removal"""
    user_id = query.from_user.id
    user = await db_service.get_user(user_id)
    
    if not user or not user.get('wishlist'):
        await query.edit_message_text(
            "Your wishlist is empty!",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    await query.edit_message_text(
        "🗑️ *Remove Wishlist Item*\n\nSelect an item to remove:",
        parse_mode="Markdown",
        reply_markup=wishlist_remove_keyboard(user['wishlist'])
    )


async def handle_wishlist_delete(query, data):
    """Delete wishlist item"""
    item_id = data.replace("delwish_", "")
    user_id = query.from_user.id
    
    user = await db_service.get_user(user_id)
    if user:
        wishlist = [item for item in user.get('wishlist', []) if item.get('id') != item_id]
        await db_service.update_user(user_id, {"wishlist": wishlist})
    
    await query.edit_message_text(
        "✅ Item removed from your wishlist!",
        reply_markup=wishlist_manage_keyboard()
    )


async def show_my_events(query):
    """Show events user is participating in"""
    user_id = query.from_user.id
    events = await db_service.get_user_events(user_id)
    
    if not events:
        await query.edit_message_text(
            "📋 *My Events*\n\n"
            "You're not participating in any birthday collections yet.\n\n"
            "You'll receive invitations when a teammate's birthday approaches!",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    await query.edit_message_text(
        "📋 *My Events*\n\nSelect an event to view details:",
        parse_mode="Markdown",
        reply_markup=events_list_keyboard(events)
    )


async def handle_accept_invitation(query, data):
    """Handle accepting a birthday event invitation"""
    event_id = data.replace("accept_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event:
        await query.edit_message_text(
            "This event no longer exists.",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    # Check if user is the birthday person
    if event.get('birthday_person_id') == user_id:
        await query.edit_message_text(
            "🎂 This is YOUR birthday! Enjoy the surprise!",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    # Add participant
    await db_service.add_participant_to_event(event_id, user_id)
    
    # Create contribution record
    existing_contribution = await db_service.get_contribution(event_id, user_id)
    if not existing_contribution:
        contribution = Contribution(
            event_id=event_id,
            user_id=user_id
        )
        await db_service.create_contribution(contribution.model_dump())
    
    await query.edit_message_text(
        f"✅ *You're in!*\n\n"
        f"You've joined the gift collection for *{event.get('birthday_person_name')}*.\n\n"
        f"Birthday: {event.get('birthday_date')}\n\n"
        f"Use 'My Events' to vote, contribute, or become the organizer!",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def handle_skip_invitation(query, data):
    """Handle skipping a birthday event invitation"""
    event_id = data.replace("skip_", "")
    user_id = query.from_user.id
    
    # Create a declined contribution record
    existing_contribution = await db_service.get_contribution(event_id, user_id)
    if not existing_contribution:
        contribution = Contribution(
            event_id=event_id,
            user_id=user_id,
            status=ContributionStatus.DECLINED
        )
        await db_service.create_contribution(contribution.model_dump())
    else:
        await db_service.update_contribution(event_id, user_id, {"status": "declined"})
    
    await query.edit_message_text(
        "👍 No problem! You can always join later from 'My Events' if you change your mind.",
        reply_markup=back_to_menu_keyboard()
    )


async def show_event_details(query, data):
    """Show details of a specific event"""
    event_id = data.replace("event_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event:
        await query.edit_message_text(
            "Event not found.",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    status_text = {
        'upcoming': '📅 Upcoming',
        'voting': '🗳️ Voting in progress',
        'finalized': '✅ Gift finalized',
        'completed': '🎉 Completed'
    }.get(event.get('status'), 'Unknown')
    
    organizer_text = "None (be the first!)" if not event.get('organizer_id') else "Assigned"
    
    # Get contribution stats
    contributions = await db_service.get_event_contributions(event_id)
    paid_count = sum(1 for c in contributions if c.get('status') == 'paid')
    
    # Check if current user has contributed
    user_contribution = await db_service.get_contribution(event_id, user_id)
    has_contributed = user_contribution and user_contribution.get('status') == 'paid'
    
    text = (
        f"🎂 *Birthday Collection*\n\n"
        f"👤 For: {event.get('birthday_person_name', 'Unknown')}\n"
        f"📅 Date: {event.get('birthday_date', 'Unknown')}\n"
        f"📊 Status: {status_text}\n"
        f"👑 Organizer: {organizer_text}\n"
        f"👥 Participants: {len(event.get('participants', []))}\n"
        f"💰 Contributions: {paid_count}\n"
    )
    
    if event.get('selected_gift'):
        text += f"\n🎁 Selected Gift: {event.get('selected_gift')}"
    
    if event.get('total_price'):
        per_person = event['total_price'] / max(len(event.get('participants', [])), 1)
        text += f"\n💵 Total: ${event['total_price']:.2f} (${per_person:.2f}/person)"
    
    if event.get('payment_details'):
        text += f"\n💳 Payment: {event.get('payment_details')}"
    
    is_organizer = event.get('organizer_id') == user_id
    has_organizer = event.get('organizer_id') is not None
    
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=event_actions_keyboard(event_id, is_organizer, has_organizer, has_contributed)
    )


async def handle_join_event(query, data):
    """Handle joining a birthday collection"""
    event_id = data.replace("join_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event:
        await query.message.reply_text("This event no longer exists.")
        return
    
    # Check if user is the birthday person
    if event.get('birthday_person_id') == user_id:
        await query.message.reply_text(
            "🎂 This is YOUR birthday! You can't join your own collection.\n"
            "Sit back and enjoy the surprise!"
        )
        return
    
    # Add participant
    await db_service.add_participant_to_event(event_id, user_id)
    
    # Create contribution record
    existing_contribution = await db_service.get_contribution(event_id, user_id)
    if not existing_contribution:
        contribution = Contribution(
            event_id=event_id,
            user_id=user_id
        )
        await db_service.create_contribution(contribution.model_dump())
    
    # Send private message with event details
    await query.message.reply_text(
        f"🎉 You've joined the birthday collection for {event.get('birthday_person_name')}!\n\n"
        "I'll send you updates and voting options here in our private chat.",
        reply_markup=main_menu_keyboard()
    )


async def handle_contribute(query, data):
    """Mark contribution as paid or toggle it"""
    event_id = data.replace("contribute_", "")
    user_id = query.from_user.id
    
    contribution = await db_service.get_contribution(event_id, user_id)
    if not contribution:
        await query.edit_message_text(
            "You're not part of this collection.",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    # Toggle contribution status
    if contribution.get('status') == 'paid':
        # Unmark contribution
        await db_service.update_contribution(event_id, user_id, {
            "status": "pending",
            "marked_paid_at": None
        })
    else:
        # Mark as paid
        await db_service.update_contribution(event_id, user_id, {
            "status": "paid",
            "marked_paid_at": datetime.now(timezone.utc)
        })
    
    # Return to event details
    await show_event_details(query, f"event_{event_id}")


async def show_voting_options(query, data):
    """Show wishlist items for voting"""
    event_id = data.replace("vote_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event:
        await query.edit_message_text("Event not found.", reply_markup=back_to_menu_keyboard())
        return
    
    wishlist = event.get('wishlist_snapshot', [])
    if not wishlist:
        await query.edit_message_text(
            "📋 No wishlist items to vote on.\n\n"
            "The birthday person hasn't added any items to their wishlist.",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    await query.edit_message_text(
        f"🗳️ *Vote for Gift*\n\n"
        f"For: {event.get('birthday_person_name')}\n\n"
        "Select items you think we should get:",
        parse_mode="Markdown",
        reply_markup=wishlist_keyboard(wishlist, event_id, user_id)
    )


async def handle_vote(query, data):
    """Handle vote for wishlist item"""
    # Format: vw_{short_event_id}_{item_index}
    parts = data.replace("vw_", "").split("_")
    short_event_id = parts[0]
    item_idx = int(parts[1])
    user_id = query.from_user.id
    
    # Find event by short ID
    event = await db_service.get_event_by_short_id(short_event_id)
    if not event:
        await query.edit_message_text("Event not found.", reply_markup=back_to_menu_keyboard())
        return
    
    event_id = event.get('id')
    wishlist = event.get('wishlist_snapshot', [])
    
    if item_idx < len(wishlist):
        item_id = wishlist[item_idx].get('id')
        await db_service.vote_for_wishlist_item(event_id, item_id, user_id)
    
    # Refresh voting view
    event = await db_service.get_event(event_id)
    wishlist = event.get('wishlist_snapshot', [])
    
    await query.edit_message_text(
        f"🗳️ *Vote for Gift*\n\n"
        f"For: {event.get('birthday_person_name')}\n\n"
        "Select items you think we should get:",
        parse_mode="Markdown",
        reply_markup=wishlist_keyboard(wishlist, event_id, user_id)
    )


async def handle_short_event_back(query, data):
    """Handle back button from wishlist voting (uses short event ID)"""
    short_event_id = data.replace("ev_", "")
    
    event = await db_service.get_event_by_short_id(short_event_id)
    if not event:
        await query.edit_message_text("Event not found.", reply_markup=back_to_menu_keyboard())
        return
    
    # Show event details
    await show_event_details(query, f"event_{event.get('id')}")


async def handle_discussion_request(query, data):
    """Handle request to join/create discussion group"""
    event_id = data.replace("discuss_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event:
        await query.edit_message_text("Event not found.", reply_markup=back_to_menu_keyboard())
        return
    
    discussion_group = await db_service.get_discussion_group(event_id)
    is_organizer = event.get('organizer_id') == user_id
    
    if discussion_group and discussion_group.get('invite_link'):
        # Group exists, send invite link
        await query.edit_message_text(
            f"💬 *Discussion Group*\n\n"
            f"Join the discussion for *{event.get('birthday_person_name')}*'s gift:\n\n"
            f"👉 {discussion_group.get('invite_link')}",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
            disable_web_page_preview=True
        )
    elif is_organizer:
        # Organizer can set up a discussion group
        await query.edit_message_text(
            "💬 *Create Discussion Group*\n\n"
            "To create a discussion group:\n\n"
            "1️⃣ Create a new Telegram group\n"
            "2️⃣ Add participants (NOT the birthday person!)\n"
            "3️⃣ Create an invite link (Group Settings → Invite Link)\n"
            "4️⃣ Send me the invite link here\n\n"
            "Send the link now, or /cancel to go back.",
            parse_mode="Markdown"
        )
        user_states[user_id] = {
            "state": "awaiting_discussion_link",
            "event_id": event_id
        }
    else:
        # Not organizer, no group yet
        if event.get('organizer_id'):
            await query.edit_message_text(
                "💬 *Discussion Group*\n\n"
                "No discussion group has been created yet.\n\n"
                "The organizer can set one up. Ask them to click 'Join Discussion' to create it!",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard()
            )
        else:
            await query.edit_message_text(
                "💬 *Discussion Group*\n\n"
                "No discussion group has been created yet.\n\n"
                "Become the organizer to create a discussion group!",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard()
            )


async def handle_become_organizer(query, data):
    """Handle becoming an organizer"""
    event_id = data.replace("organize_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event:
        await query.edit_message_text("Event not found.", reply_markup=back_to_menu_keyboard())
        return
    
    if event.get('organizer_id'):
        await query.edit_message_text(
            "This event already has an organizer.",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    await db_service.update_event(event_id, {"organizer_id": user_id})
    
    await query.edit_message_text(
        "👑 *You are now the Organizer!*\n\n"
        "Responsibilities:\n"
        "• Monitor contribution count\n"
        "• Finalize the gift selection\n"
        "• Enter total price and payment details\n"
        "• Coordinate the gift purchase\n\n"
        "You can step down anytime if needed.",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def show_finalize_options(query, data):
    """Show options for finalizing gift"""
    event_id = data.replace("finalize_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event or event.get('organizer_id') != user_id:
        await query.edit_message_text(
            "Only the organizer can finalize the gift.",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    wishlist = event.get('wishlist_snapshot', [])
    
    await query.edit_message_text(
        "✅ *Finalize Gift Selection*\n\n"
        "Select the gift to purchase or enter a custom gift:",
        parse_mode="Markdown",
        reply_markup=finalize_options_keyboard(event_id, wishlist)
    )


async def handle_gift_selection(query, data):
    """Handle gift selection from wishlist"""
    # Format: sg_{short_event_id}_{item_index}
    parts = data.replace("sg_", "").split("_")
    short_event_id = parts[0]
    item_idx = int(parts[1])
    user_id = query.from_user.id
    
    event = await db_service.get_event_by_short_id(short_event_id)
    if not event or event.get('organizer_id') != user_id:
        await query.edit_message_text("Only the organizer can finalize.", reply_markup=back_to_menu_keyboard())
        return
    
    event_id = event.get('id')
    wishlist = event.get('wishlist_snapshot', [])
    
    # Find selected item by index
    if item_idx < len(wishlist):
        selected_item = wishlist[item_idx]
        
        await db_service.update_event(event_id, {
            "selected_gift": selected_item.get('title'),
            "status": "finalized",
            "finalized_at": datetime.now(timezone.utc)
        })
        
        user_states[user_id] = {
            "state": "awaiting_price",
            "event_id": event_id
        }
        
        await query.edit_message_text(
            f"🎁 *Gift Selected!*\n\n"
            f"Selected: {selected_item.get('title')}\n\n"
            "Now enter the total price (just the number):\n"
            "Example: `49.99`",
            parse_mode="Markdown"
        )


async def prompt_custom_gift(query, data):
    """Prompt for custom gift entry"""
    # Format: cg_{short_event_id}
    short_event_id = data.replace("cg_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event_by_short_id(short_event_id)
    if not event:
        await query.edit_message_text("Event not found.", reply_markup=back_to_menu_keyboard())
        return
    
    event_id = event.get('id')
    
    user_states[user_id] = {
        "state": "awaiting_custom_gift",
        "event_id": event_id
    }
    
    await query.edit_message_text(
        "✍️ *Custom Gift*\n\n"
        "Enter the gift description:",
        parse_mode="Markdown"
    )


async def handle_organizer_stepdown(query, data):
    """Handle organizer stepping down"""
    event_id = data.replace("stepdown_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event or event.get('organizer_id') != user_id:
        return
    
    await db_service.update_event(event_id, {"organizer_id": None})
    
    await query.edit_message_text(
        "You've stepped down as organizer.\n"
        "Another participant can now take over.",
        reply_markup=back_to_menu_keyboard()
    )


async def handle_decline_participation(query, data):
    """Handle declining participation"""
    event_id = data.replace("decline_", "")
    user_id = query.from_user.id
    
    await db_service.update_contribution(event_id, user_id, {"status": "declined"})
    
    await query.edit_message_text(
        "You've declined participation in this collection.\n"
        "No worries! You can join future collections.",
        reply_markup=back_to_menu_keyboard()
    )


async def show_contributions_summary(query, data):
    """Show anonymous contribution summary to organizer"""
    event_id = data.replace("view_contrib_", "")
    user_id = query.from_user.id
    
    event = await db_service.get_event(event_id)
    if not event or event.get('organizer_id') != user_id:
        await query.edit_message_text(
            "Only the organizer can view contribution details.",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    contributions = await db_service.get_event_contributions(event_id)
    
    paid = sum(1 for c in contributions if c.get('status') == 'paid')
    pending = sum(1 for c in contributions if c.get('status') == 'pending')
    declined = sum(1 for c in contributions if c.get('status') == 'declined')
    
    await query.edit_message_text(
        f"📊 *Contribution Summary*\n\n"
        f"✅ Paid: {paid}\n"
        f"⏳ Pending: {pending}\n"
        f"❌ Declined: {declined}\n\n"
        f"Total participants: {len(contributions)}",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def show_help(query):
    """Show help message"""
    await query.edit_message_text(
        "❓ *Birthday Organizer Bot Help*\n\n"
        "*For Team Members:*\n"
        "1. Set your birthday in the bot\n"
        "2. Add items to your wishlist\n"
        "3. When a birthday is announced, click 'Join Collection'\n"
        "4. Vote for gifts, contribute, and discuss!\n\n"
        "*For Organizers:*\n"
        "• Anyone can become an organizer\n"
        "• Monitor contributions (anonymous count)\n"
        "• Finalize gift selection\n"
        "• Enter price and payment details\n\n"
        "*Commands:*\n"
        "/start - Main menu\n"
        "/help - This help message\n\n"
        "Questions? Contact your team admin!",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages based on user state"""
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    
    user_id = update.effective_user.id
    text = update.message.text
    
    state_data = user_states.get(user_id, {})
    state = state_data.get("state")
    
    if state == "awaiting_wishlist_item":
        await handle_wishlist_item_input(update, text)
    elif state == "awaiting_custom_gift":
        await handle_custom_gift_input(update, text, state_data.get("event_id"))
    elif state == "awaiting_price":
        await handle_price_input(update, text, state_data.get("event_id"))
    elif state == "awaiting_payment_details":
        await handle_payment_details_input(update, text, state_data.get("event_id"))
    elif state == "awaiting_discussion_link":
        await handle_discussion_link_input(update, text, state_data.get("event_id"))
    else:
        await update.message.reply_text(
            "Use the menu to interact with me!",
            reply_markup=main_menu_keyboard()
        )


async def handle_wishlist_item_input(update: Update, text: str):
    """Process wishlist item input"""
    user_id = update.effective_user.id
    
    # Parse input: "Item name" or "Item name | URL"
    parts = text.split("|")
    title = parts[0].strip()
    url = parts[1].strip() if len(parts) > 1 else None
    
    item = WishlistItem(title=title, url=url)
    
    user = await db_service.get_user(user_id)
    wishlist = user.get('wishlist', []) if user else []
    wishlist.append(item.model_dump())
    
    await db_service.update_user(user_id, {"wishlist": wishlist})
    
    # Clear state
    user_states.pop(user_id, None)
    
    await update.message.reply_text(
        f"✅ Added to your wishlist: *{title}*",
        parse_mode="Markdown",
        reply_markup=wishlist_manage_keyboard()
    )


async def handle_custom_gift_input(update: Update, text: str, event_id: str):
    """Process custom gift input"""
    user_id = update.effective_user.id
    
    await db_service.update_event(event_id, {
        "selected_gift": text,
        "status": "finalized",
        "finalized_at": datetime.now(timezone.utc)
    })
    
    user_states[user_id] = {
        "state": "awaiting_price",
        "event_id": event_id
    }
    
    await update.message.reply_text(
        f"🎁 *Gift Selected!*\n\n"
        f"Selected: {text}\n\n"
        "Now enter the total price (just the number):\n"
        "Example: `49.99`",
        parse_mode="Markdown"
    )


async def handle_price_input(update: Update, text: str, event_id: str):
    """Process price input"""
    user_id = update.effective_user.id
    
    try:
        price = float(text.replace("$", "").replace(",", "").strip())
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number. Example: `49.99`",
            parse_mode="Markdown"
        )
        return
    
    await db_service.update_event(event_id, {"total_price": price})
    
    user_states[user_id] = {
        "state": "awaiting_payment_details",
        "event_id": event_id
    }
    
    await update.message.reply_text(
        f"💵 *Price Set: ${price:.2f}*\n\n"
        "Now enter the payment details (e.g., Venmo, PayPal, bank details):",
        parse_mode="Markdown"
    )


async def handle_payment_details_input(update: Update, text: str, event_id: str):
    """Process payment details input and notify participants"""
    user_id = update.effective_user.id
    bot = update.get_bot()
    
    await db_service.update_event(event_id, {"payment_details": text})
    
    # Clear state
    user_states.pop(user_id, None)
    
    event = await db_service.get_event(event_id)
    participants_count = len(event.get('participants', []))
    total_price = event.get('total_price', 0)
    per_person = total_price / max(participants_count, 1)
    
    await update.message.reply_text(
        f"✅ *Gift Finalized!*\n\n"
        f"🎁 Gift: {event.get('selected_gift')}\n"
        f"💵 Total: ${total_price:.2f}\n"
        f"👥 Per person: ${per_person:.2f}\n"
        f"💳 Payment: {text}\n\n"
        "Notifying all participants now...",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    
    # Notify all participants about finalized gift and payment details
    for participant_id in event.get('participants', []):
        if participant_id == user_id:
            continue  # Skip organizer
        
        try:
            await bot.send_message(
                chat_id=participant_id,
                text=(
                    f"🎁 *Gift Collection Finalized!*\n\n"
                    f"For: *{event.get('birthday_person_name')}*'s birthday\n\n"
                    f"🎁 Gift: {event.get('selected_gift')}\n"
                    f"💵 Your share: *${per_person:.2f}*\n\n"
                    f"💳 *Payment Details:*\n{text}\n\n"
                    f"Please send your contribution and mark it as paid in the bot!"
                ),
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            logger.debug(f"Could not notify participant {participant_id}: {e}")


async def handle_discussion_link_input(update: Update, text: str, event_id: str):
    """Process discussion group invite link"""
    from models.schemas import DiscussionGroup
    
    user_id = update.effective_user.id
    
    # Handle cancel
    if text.lower() == '/cancel':
        user_states.pop(user_id, None)
        await update.message.reply_text(
            "Cancelled. No discussion group was created.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    # Validate it looks like a Telegram invite link
    if not ('t.me/' in text or 'telegram.me/' in text):
        await update.message.reply_text(
            "⚠️ That doesn't look like a Telegram invite link.\n\n"
            "Please send a valid link (e.g., https://t.me/+ABC123) or /cancel to go back."
        )
        return
    
    # Clear state
    user_states.pop(user_id, None)
    
    # Check if discussion group already exists
    existing_group = await db_service.get_discussion_group(event_id)
    if existing_group:
        await db_service.update_discussion_group(event_id, {"invite_link": text.strip()})
    else:
        # Create discussion group record
        discussion_group = DiscussionGroup(
            event_id=event_id,
            telegram_group_id=0,  # We don't have the actual group ID
            invite_link=text.strip()
        )
        await db_service.create_discussion_group(discussion_group.model_dump())
    
    # Update event with discussion group reference
    await db_service.update_event(event_id, {"discussion_group_id": 1})  # Mark as having a group
    
    event = await db_service.get_event(event_id)
    
    await update.message.reply_text(
        f"✅ *Discussion Group Created!*\n\n"
        f"For: {event.get('birthday_person_name')}'s birthday\n\n"
        f"Participants can now click 'Join Discussion' to get the invite link.\n\n"
        f"⚠️ Remember: Don't add the birthday person to the group!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "❓ *Birthday Organizer Bot Help*\n\n"
            "Use /start to access the main menu and all features!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "Message me privately for help and to set up your birthday!",
            parse_mode="Markdown"
        )



async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining a group - register them and check for upcoming birthdays"""
    if not update.message or not update.message.new_chat_members:
        return
    
    chat = update.effective_chat
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return
    
    # Make sure team exists
    team = await db_service.get_team(chat.id)
    if not team:
        return
    
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        
        # Check if user exists
        existing_user = await db_service.get_user(member.id)
        if existing_user:
            # Add to team
            await db_service.add_user_to_team(member.id, chat.id)
            await db_service.add_member_to_team(chat.id, member.id)
            
            # Check if their birthday is within 14 days
            if existing_user.get('date_of_birth') and existing_user.get('onboarded'):
                await check_and_create_immediate_event(
                    member.id, 
                    existing_user['date_of_birth'], 
                    context.bot
                )
                logger.info(f"Checked immediate birthday for new member {member.id} in team {chat.id}")


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages in groups to register users and check birthdays"""
    if not update.message or not update.effective_user:
        return
    
    chat = update.effective_chat
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return
    
    user = update.effective_user
    if user.is_bot:
        return
    
    # Make sure team exists
    team = await db_service.get_team(chat.id)
    if not team:
        return
    
    # Check if user is already in team
    if user.id in team.get('members', []):
        return
    
    # User is messaging in group but not registered - add them
    existing_user = await db_service.get_user(user.id)
    if existing_user:
        await db_service.add_user_to_team(user.id, chat.id)
        await db_service.add_member_to_team(chat.id, user.id)
        
        # Check if their birthday is within 14 days
        if existing_user.get('date_of_birth') and existing_user.get('onboarded'):
            await check_and_create_immediate_event(
                user.id, 
                existing_user['date_of_birth'], 
                context.bot
            )
            logger.info(f"Registered user {user.id} in team {chat.id} via group message")

