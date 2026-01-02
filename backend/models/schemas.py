"""
Pydantic models for Birthday Organizer Bot
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
import uuid


class ContributionStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    DECLINED = "declined"


class EventStatus(str, Enum):
    UPCOMING = "upcoming"
    VOTING = "voting"
    FINALIZED = "finalized"
    COMPLETED = "completed"


class WishlistItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    url: Optional[str] = None
    votes: int = 0
    voted_by: List[int] = Field(default_factory=list)  # telegram user ids


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None  # MM-DD format
    wishlist: List[WishlistItem] = Field(default_factory=list)
    teams: List[int] = Field(default_factory=list)  # team telegram chat ids
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    onboarded: bool = False


class Team(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_chat_id: int
    title: str
    members: List[int] = Field(default_factory=list)  # telegram user ids
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BirthdayEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    birthday_person_id: int  # telegram user id
    birthday_person_name: str
    team_id: int  # team telegram chat id
    birthday_date: str  # YYYY-MM-DD
    status: EventStatus = EventStatus.UPCOMING
    organizer_id: Optional[int] = None  # telegram user id
    participants: List[int] = Field(default_factory=list)  # telegram user ids who joined
    wishlist_snapshot: List[WishlistItem] = Field(default_factory=list)
    selected_gift: Optional[str] = None
    total_price: Optional[float] = None
    split_count: Optional[int] = None  # custom number of people to split cost
    payment_details: Optional[str] = None
    discussion_group_id: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    voting_started_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Contribution(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str
    user_id: int  # telegram user id
    amount: Optional[float] = None
    status: ContributionStatus = ContributionStatus.PENDING
    marked_paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DiscussionGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str
    telegram_group_id: int
    invite_link: str
    members: List[int] = Field(default_factory=list)  # telegram user ids
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# API Response Models
class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str
    telegram_id: int
    username: Optional[str]
    first_name: str
    date_of_birth: Optional[str]
    onboarded: bool


class EventResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str
    birthday_person_name: str
    birthday_date: str
    status: str
    participants_count: int
    contributions_count: int
    has_organizer: bool
