"""
Inline keyboards for Birthday Organizer Bot
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu for private chat"""
    keyboard = [
        [InlineKeyboardButton("🎂 Set My Birthday", callback_data="set_birthday")],
        [InlineKeyboardButton("🎁 My Wishlist", callback_data="view_wishlist")],
        [InlineKeyboardButton("📋 My Events", callback_data="my_events")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)


def join_collection_keyboard(event_id: str) -> InlineKeyboardMarkup:
    """Button shown in main chat to join birthday collection"""
    keyboard = [
        [InlineKeyboardButton("🎁 Join Birthday Collection", callback_data=f"join_{event_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def event_actions_keyboard(event_id: str, is_organizer: bool = False, has_organizer: bool = False) -> InlineKeyboardMarkup:
    """Actions for a birthday event participant"""
    keyboard = [
        [InlineKeyboardButton("💰 Mark as Contributed", callback_data=f"contribute_{event_id}")],
        [InlineKeyboardButton("🗳️ Vote for Gift", callback_data=f"vote_{event_id}")],
        [InlineKeyboardButton("💬 Join Discussion", callback_data=f"discuss_{event_id}")]
    ]
    
    if not has_organizer:
        keyboard.append([InlineKeyboardButton("👑 Become Organizer", callback_data=f"organize_{event_id}")])
    
    if is_organizer:
        keyboard.extend([
            [InlineKeyboardButton("✅ Finalize Gift", callback_data=f"finalize_{event_id}")],
            [InlineKeyboardButton("📊 View Contributions", callback_data=f"view_contrib_{event_id}")],
            [InlineKeyboardButton("🚫 Step Down as Organizer", callback_data=f"stepdown_{event_id}")]
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Decline Participation", callback_data=f"decline_{event_id}")])
    
    return InlineKeyboardMarkup(keyboard)


def wishlist_keyboard(items: List[dict], event_id: str, user_id: int) -> InlineKeyboardMarkup:
    """Wishlist voting keyboard"""
    keyboard = []
    for item in items:
        votes = item.get('votes', 0)
        voted = user_id in item.get('voted_by', [])
        vote_icon = "✅" if voted else "🗳️"
        title = item.get('title', 'Item')[:30]
        keyboard.append([
            InlineKeyboardButton(
                f"{vote_icon} {title} ({votes} votes)",
                callback_data=f"votewish_{event_id}_{item['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"event_{event_id}")])
    return InlineKeyboardMarkup(keyboard)


def confirm_keyboard(action: str, event_id: str) -> InlineKeyboardMarkup:
    """Generic confirmation keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{action}_{event_id}"),
            InlineKeyboardButton("❌ No", callback_data=f"cancel_{action}_{event_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def finalize_options_keyboard(event_id: str, wishlist: List[dict]) -> InlineKeyboardMarkup:
    """Options for finalizing a gift"""
    keyboard = []
    for item in wishlist:
        votes = item.get('votes', 0)
        title = item.get('title', 'Item')[:25]
        keyboard.append([
            InlineKeyboardButton(
                f"🎁 {title} ({votes} votes)",
                callback_data=f"selectgift_{event_id}_{item['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("✍️ Custom Gift", callback_data=f"customgift_{event_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Cancel", callback_data=f"event_{event_id}")])
    return InlineKeyboardMarkup(keyboard)


def wishlist_manage_keyboard() -> InlineKeyboardMarkup:
    """Manage personal wishlist"""
    keyboard = [
        [InlineKeyboardButton("➕ Add Item", callback_data="add_wishlist_item")],
        [InlineKeyboardButton("🗑️ Remove Item", callback_data="remove_wishlist_item")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def wishlist_remove_keyboard(items: List[dict]) -> InlineKeyboardMarkup:
    """Select item to remove from wishlist"""
    keyboard = []
    for item in items:
        title = item.get('title', 'Item')[:30]
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {title}", callback_data=f"delwish_{item['id']}")
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Cancel", callback_data="view_wishlist")])
    return InlineKeyboardMarkup(keyboard)


def events_list_keyboard(events: List[dict]) -> InlineKeyboardMarkup:
    """List of events user is participating in"""
    keyboard = []
    for event in events[:10]:  # Limit to 10
        name = event.get('birthday_person_name', 'Unknown')[:20]
        date = event.get('birthday_date', '')
        status_emoji = {
            'upcoming': '📅',
            'voting': '🗳️',
            'finalized': '✅',
            'completed': '🎉'
        }.get(event.get('status'), '📋')
        
        keyboard.append([
            InlineKeyboardButton(
                f"{status_emoji} {name} - {date}",
                callback_data=f"event_{event['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Simple back button"""
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)


def month_keyboard() -> InlineKeyboardMarkup:
    """Month selection for birthday"""
    months = [
        ("Jan", "01"), ("Feb", "02"), ("Mar", "03"), ("Apr", "04"),
        ("May", "05"), ("Jun", "06"), ("Jul", "07"), ("Aug", "08"),
        ("Sep", "09"), ("Oct", "10"), ("Nov", "11"), ("Dec", "12")
    ]
    keyboard = []
    row = []
    for name, num in months:
        row.append(InlineKeyboardButton(name, callback_data=f"month_{num}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    keyboard.append([InlineKeyboardButton("⬅️ Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def day_keyboard(month: str) -> InlineKeyboardMarkup:
    """Day selection based on month"""
    days_in_month = {
        "01": 31, "02": 29, "03": 31, "04": 30, "05": 31, "06": 30,
        "07": 31, "08": 31, "09": 30, "10": 31, "11": 30, "12": 31
    }
    max_days = days_in_month.get(month, 31)
    
    keyboard = []
    row = []
    for day in range(1, max_days + 1):
        row.append(InlineKeyboardButton(str(day), callback_data=f"day_{month}_{day:02d}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="set_birthday")])
    return InlineKeyboardMarkup(keyboard)
