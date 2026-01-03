"""
Database service for Birthday Organizer Bot
"""
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import os
import logging

# Load environment
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self):
        self.client = AsyncIOMotorClient(os.environ['MONGO_URL'])
        self.db = self.client[os.environ['DB_NAME']]
        
    # User operations
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        return await self.db.users.find_one(
            {"telegram_id": telegram_id}, 
            {"_id": 0}
        )
    
    async def create_user(self, user_data: Dict) -> Dict:
        user_data['created_at'] = user_data['created_at'].isoformat()
        await self.db.users.insert_one(user_data)
        return user_data
    
    async def update_user(self, telegram_id: int, update_data: Dict) -> bool:
        result = await self.db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def add_user_to_team(self, telegram_id: int, team_id: int) -> bool:
        result = await self.db.users.update_one(
            {"telegram_id": telegram_id},
            {"$addToSet": {"teams": team_id}}
        )
        return result.modified_count > 0
    
    async def get_users_by_team(self, team_id: int) -> List[Dict]:
        return await self.db.users.find(
            {"teams": team_id},
            {"_id": 0}
        ).to_list(1000)
    
    # Team operations
    async def get_team(self, telegram_chat_id: int) -> Optional[Dict]:
        return await self.db.teams.find_one(
            {"telegram_chat_id": telegram_chat_id},
            {"_id": 0}
        )
    
    async def create_team(self, team_data: Dict) -> Dict:
        team_data['created_at'] = team_data['created_at'].isoformat()
        await self.db.teams.insert_one(team_data)
        return team_data
    
    async def add_member_to_team(self, team_id: int, user_id: int) -> bool:
        result = await self.db.teams.update_one(
            {"telegram_chat_id": team_id},
            {"$addToSet": {"members": user_id}}
        )
        return result.modified_count > 0
    
    async def get_all_teams(self) -> List[Dict]:
        return await self.db.teams.find({}, {"_id": 0}).to_list(1000)
    
    # Birthday Event operations
    async def get_event(self, event_id: str) -> Optional[Dict]:
        return await self.db.birthday_events.find_one(
            {"id": event_id},
            {"_id": 0}
        )
    
    async def get_event_by_short_id(self, short_id: str) -> Optional[Dict]:
        """Find event by first 8 characters of ID"""
        return await self.db.birthday_events.find_one(
            {"id": {"$regex": f"^{short_id}"}},
            {"_id": 0}
        )
    
    async def get_event_by_person_and_date(self, birthday_person_id: int, birthday_date: str, team_id: int) -> Optional[Dict]:
        return await self.db.birthday_events.find_one(
            {
                "birthday_person_id": birthday_person_id,
                "birthday_date": birthday_date,
                "team_id": team_id
            },
            {"_id": 0}
        )
    
    async def create_event(self, event_data: Dict) -> Dict:
        event_data['created_at'] = event_data['created_at'].isoformat()
        if event_data.get('voting_started_at'):
            event_data['voting_started_at'] = event_data['voting_started_at'].isoformat()
        await self.db.birthday_events.insert_one(event_data)
        return event_data
    
    async def update_event(self, event_id: str, update_data: Dict) -> bool:
        # Convert datetime fields to ISO strings
        for key in ['voting_started_at', 'finalized_at', 'completed_at']:
            if key in update_data and isinstance(update_data[key], datetime):
                update_data[key] = update_data[key].isoformat()
        
        result = await self.db.birthday_events.update_one(
            {"id": event_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def add_participant_to_event(self, event_id: str, user_id: int) -> bool:
        result = await self.db.birthday_events.update_one(
            {"id": event_id},
            {"$addToSet": {"participants": user_id}}
        )
        return result.modified_count > 0
    
    async def get_upcoming_birthdays(self, days_ahead: int = 14) -> List[Dict]:
        """Get users with birthdays in the next X days"""
        today = datetime.now(timezone.utc)
        dates_to_check = []
        
        for i in range(days_ahead + 1):
            check_date = today + timedelta(days=i)
            dates_to_check.append(check_date.strftime("%m-%d"))
        
        users = await self.db.users.find(
            {
                "date_of_birth": {"$in": dates_to_check},
                "onboarded": True
            },
            {"_id": 0}
        ).to_list(1000)
        
        return users
    
    async def get_events_by_status(self, status: str) -> List[Dict]:
        return await self.db.birthday_events.find(
            {"status": status},
            {"_id": 0}
        ).to_list(1000)
    
    async def get_user_events(self, user_id: int) -> List[Dict]:
        """Get events where user is participant but not birthday person"""
        return await self.db.birthday_events.find(
            {
                "participants": user_id,
                "birthday_person_id": {"$ne": user_id}
            },
            {"_id": 0}
        ).to_list(100)
    
    async def get_events_needing_reminders(self, days_before: int) -> List[Dict]:
        """Get events that need reminders X days before birthday"""
        target_date = (datetime.now(timezone.utc) + timedelta(days=days_before)).strftime("%Y-%m-%d")
        return await self.db.birthday_events.find(
            {
                "birthday_date": target_date,
                "status": {"$in": ["voting", "finalized"]}
            },
            {"_id": 0}
        ).to_list(1000)
    
    async def get_todays_birthdays(self) -> List[Dict]:
        """Get events with birthday today"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return await self.db.birthday_events.find(
            {"birthday_date": today},
            {"_id": 0}
        ).to_list(1000)
    
    # Contribution operations
    async def get_contribution(self, event_id: str, user_id: int) -> Optional[Dict]:
        return await self.db.contributions.find_one(
            {"event_id": event_id, "user_id": user_id},
            {"_id": 0}
        )
    
    async def create_contribution(self, contribution_data: Dict) -> Dict:
        contribution_data['created_at'] = contribution_data['created_at'].isoformat()
        if contribution_data.get('marked_paid_at'):
            contribution_data['marked_paid_at'] = contribution_data['marked_paid_at'].isoformat()
        await self.db.contributions.insert_one(contribution_data)
        return contribution_data
    
    async def update_contribution(self, event_id: str, user_id: int, update_data: Dict) -> bool:
        if 'marked_paid_at' in update_data and isinstance(update_data['marked_paid_at'], datetime):
            update_data['marked_paid_at'] = update_data['marked_paid_at'].isoformat()
        
        result = await self.db.contributions.update_one(
            {"event_id": event_id, "user_id": user_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def get_event_contributions(self, event_id: str) -> List[Dict]:
        return await self.db.contributions.find(
            {"event_id": event_id},
            {"_id": 0}
        ).to_list(1000)
    
    async def get_paid_contributions_count(self, event_id: str) -> int:
        return await self.db.contributions.count_documents(
            {"event_id": event_id, "status": "paid"}
        )
    
    async def get_pending_contributions(self, event_id: str) -> List[Dict]:
        return await self.db.contributions.find(
            {"event_id": event_id, "status": "pending"},
            {"_id": 0}
        ).to_list(1000)
    
    # Discussion Group operations
    async def get_discussion_group(self, event_id: str) -> Optional[Dict]:
        return await self.db.discussion_groups.find_one(
            {"event_id": event_id},
            {"_id": 0}
        )
    
    async def create_discussion_group(self, group_data: Dict) -> Dict:
        group_data['created_at'] = group_data['created_at'].isoformat()
        await self.db.discussion_groups.insert_one(group_data)
        return group_data
    
    async def update_discussion_group(self, event_id: str, update_data: Dict) -> bool:
        result = await self.db.discussion_groups.update_one(
            {"event_id": event_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def add_member_to_discussion_group(self, event_id: str, user_id: int) -> bool:
        result = await self.db.discussion_groups.update_one(
            {"event_id": event_id},
            {"$addToSet": {"members": user_id}}
        )
        return result.modified_count > 0
    
    # Wishlist vote operations
    async def vote_for_wishlist_item(self, event_id: str, item_id: str, user_id: int) -> bool:
        """Vote for a wishlist item - single vote only, can change vote"""
        event = await self.get_event(event_id)
        if not event:
            return False
        
        wishlist = event.get('wishlist_snapshot', [])
        already_voted_this = False
        
        # First, remove user's vote from ALL items
        for item in wishlist:
            voted_by = item.get('voted_by', [])
            if user_id in voted_by:
                if item['id'] == item_id:
                    already_voted_this = True
                voted_by.remove(user_id)
                item['votes'] = max(0, item.get('votes', 1) - 1)
                item['voted_by'] = voted_by
        
        # If user clicked the same item, just remove vote (toggle off)
        # If user clicked different item, add vote to new item
        if not already_voted_this:
            for item in wishlist:
                if item['id'] == item_id:
                    item['votes'] = item.get('votes', 0) + 1
                    item.setdefault('voted_by', []).append(user_id)
                    break
        
        return await self.update_event(event_id, {"wishlist_snapshot": wishlist})
    
    async def update_user_wishlist_in_active_events(self, user_id: int, new_wishlist: List[Dict]) -> int:
        """Update wishlist_snapshot in all active/voting events for a user
        
        Args:
            user_id: Telegram user ID of the birthday person
            new_wishlist: Updated wishlist items
            
        Returns:
            Number of events updated
        """
        # Find all events where this user is the birthday person and status is 'upcoming' or 'voting'
        events = await self.db.birthday_events.find(
            {
                "birthday_person_id": user_id,
                "status": {"$in": ["upcoming", "voting"]}
            },
            {"_id": 0, "id": 1, "wishlist_snapshot": 1}
        ).to_list(100)
        
        if not events:
            return 0
        
        # For each event, preserve existing votes but update items
        updated_count = 0
        for event in events:
            old_wishlist = event.get('wishlist_snapshot', [])
            
            # Create a mapping of old items by ID to preserve votes
            old_items_map = {item.get('id'): item for item in old_wishlist}
            
            # Build updated wishlist with preserved votes
            updated_wishlist = []
            for new_item in new_wishlist:
                item_id = new_item.get('id')
                if item_id in old_items_map:
                    # Item already exists - preserve votes and voted_by
                    old_item = old_items_map[item_id]
                    updated_item = new_item.copy()
                    updated_item['votes'] = old_item.get('votes', 0)
                    updated_item['voted_by'] = old_item.get('voted_by', [])
                    updated_wishlist.append(updated_item)
                else:
                    # New item - use defaults from model
                    updated_wishlist.append(new_item)
            
            # Update the event
            result = await self.update_event(event.get('id'), {"wishlist_snapshot": updated_wishlist})
            if result:
                updated_count += 1
        
        logger.info(f"Updated wishlist in {updated_count} active events for user {user_id}")
        return updated_count


# Global instance
db_service = DatabaseService()
