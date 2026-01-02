# Birthday Organizer Bot - PRD & Architecture

## Original Problem Statement
Build a Telegram-first micro-SaaS called "Birthday Organizer Bot" that:
- Eliminates manual coordination of birthday gift collections in teams
- Keeps main work chat clean from discussions and finances
- Allows optional private discussions for gifts
- Lets participants vote on wishlist items
- Allows one organizer per event to manage contributions and finalize purchases

## User Personas
1. **Team Member** - Sets birthday, adds wishlist, participates in collections
2. **Organizer** - Manages gift selection, payment coordination, purchases
3. **Birthday Person** - Receives surprise celebration (excluded from coordination)

## Core Requirements
- [x] Bot posts ONLY birthday greetings in main chat
- [x] Private 1:1 onboarding (DOB, wishlist with text+links)
- [x] 2-week advance notifications
- [x] Wishlist voting system
- [x] One organizer per event
- [x] Anonymous contribution tracking
- [x] Payment details distribution
- [x] Automated reminders (2 weeks, 3 days, 1 day)
- [x] Birthday greetings on the day
- [ ] Optional discussion group creation (partial - requires group creation permissions)

## What's Been Implemented (Jan 2, 2026)

### Backend Architecture
```
/app/backend/
├── server.py          # FastAPI + Telegram webhook + lifecycle
├── bot/
│   ├── handlers.py    # All Telegram command & callback handlers
│   ├── keyboards.py   # Inline keyboard builders
│   └── scheduler.py   # APScheduler for reminders
├── services/
│   └── database.py    # MongoDB operations
└── models/
    └── schemas.py     # Pydantic models
```

### Database Schema (MongoDB)
- **users**: telegram_id, username, first_name, date_of_birth (MM-DD), wishlist[], teams[]
- **teams**: telegram_chat_id, title, members[]
- **birthday_events**: birthday_person_id, team_id, birthday_date, status, organizer_id, participants[], wishlist_snapshot[], selected_gift, total_price, payment_details
- **contributions**: event_id, user_id, status (pending/paid/declined), amount
- **discussion_groups**: event_id, telegram_group_id, invite_link, members[]

### Bot Commands & Handlers
| Command/Callback | Description |
|-----------------|-------------|
| /start | Onboarding (private) / Team registration (group) |
| /help | Help message |
| set_birthday | Month/day picker for DOB |
| view_wishlist | Manage personal wishlist |
| my_events | View participating events |
| join_{event_id} | Join birthday collection |
| contribute_{event_id} | Mark contribution as paid |
| vote_{event_id} | Vote on wishlist items |
| organize_{event_id} | Become organizer |
| finalize_{event_id} | Finalize gift selection |
| discuss_{event_id} | Join/create discussion |

### Scheduler Jobs
- **9:00 AM**: Check upcoming birthdays (2 weeks), send greetings
- **10:00 AM**: 3-day and 1-day reminders
- **11:00 AM**: Organizer reminders (7 days after finalization)

### API Endpoints
- `GET /api/health` - Health check
- `GET /api/stats` - User/team/event counts
- `POST /api/telegram/webhook` - Telegram updates
- `GET /api/telegram/webhook-info` - Webhook status
- `POST /api/trigger/check-birthdays` - Manual trigger

### Frontend
Simple status dashboard showing:
- Bot active status
- User/Team/Event counts
- Direct link to Telegram bot
- How-it-works feature cards

## Prioritized Backlog

### P0 - Critical
- All implemented ✅

### P1 - Important
- [ ] Discussion group auto-creation (requires bot admin in team group)
- [ ] Notification when organizer finalizes to all participants
- [ ] Birthday person exclusion from notifications

### P2 - Nice to Have
- [ ] Multi-language support
- [ ] Customizable greeting messages
- [ ] Gift budget suggestions based on team size
- [ ] Integration with payment services (Stripe, PayPal)
- [ ] Event history and statistics for teams

## Next Tasks
1. Test bot with real Telegram interactions
2. Add error handling for edge cases (user not in any team, etc.)
3. Implement push notifications to participants when organizer finalizes
4. Add admin commands for bot management
