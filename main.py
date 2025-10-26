import asyncio
import logging
from typing import Optional, Tuple
from telethon import TelegramClient, events, Button, types
from telethon.errors import (
    ChatAdminRequiredError,
    MessagePinningRestrictedError,
    FloodWaitError
)

from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, DEFAULT_DELAY
from database import db_manager
from utils import (
    RateLimiter,
    TempMessageManager,
    parse_duration,
    check_admin_permissions,
    BatchProcessor
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
client = TelegramClient("bot", API_ID, API_HASH)
rate_limiter = RateLimiter(DEFAULT_DELAY)
temp_manager = TempMessageManager()

db = db_manager.get_database()
users = db.users
groups = db.groups

class BroadcastBot:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.setup_handlers()
    
    def setup_handlers(self):
        # Register all event handlers
        self.client.add_event_handler(
            self.start_handler,
            events.NewMessage(pattern="/start")
        )
        # Add other handlers similarly...
    
    @staticmethod
    async def update_user_or_group(collection, identifier: dict) -> None:
        """Update user or group record in database"""
        try:
            with db_manager.session() as db:
                collection.update_one(identifier, {"$set": identifier}, upsert=True)
        except Exception as e:
            logger.error(f"Failed to update database: {e}")
    
    async def start_handler(self, event):
        """Handle /start command"""
        try:
            if event.is_private:
                await self.update_user_or_group(
                    users,
                    {"user_id": event.sender_id}
                )
                await event.reply("Hello! I'm alive and ready. 🤖")
            else:
                await self.update_user_or_group(
                    groups,
                    {"chat_id": event.chat_id}
                )
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
    
    async def broadcast_message(
        self,
        message,
        chats: list,
        pin: bool = False,
        forward: bool = False,
        duration: Optional[timedelta] = None
    ) -> Tuple[int, int]:
        """Send broadcast message to multiple chats"""
        sent, failed = 0, 0
        
        for batch in await BatchProcessor.process_chats(chats):
            for chat in batch:
                cid = chat.get("user_id") or chat.get("chat_id")
                
                try:
                    # Rate limiting
                    await rate_limiter.wait_if_needed(cid)
                    
                    # Send message
                    if forward:
                        sent_msg = await self.client.forward_messages(cid, message)
                    else:
                        if message.media:
                            sent_msg = await self.client.send_file(
                                cid,
                                file=message.media,
                                caption=message.text or ""
                            )
                        else:
                            sent_msg = await self.client.send_message(
                                cid,
                                message.text or ""
                            )
                    
                    # Handle pinning
                    if pin and await check_admin_permissions(self.client, cid):
                        await self.client.pin_message(cid, sent_msg.id, notify=False)
                    
                    # Handle temporary messages
                    if duration:
                        temp_manager.add_message(sent_msg.id, cid, duration)
                    
                    sent += 1
                    
                except (ChatAdminRequiredError, MessagePinningRestrictedError) as e:
                    logger.warning(f"Permission error in {cid}: {e}")
                    failed += 1
                except FloodWaitError as e:
                    logger.warning(f"Rate limit hit, waiting {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    logger.error(f"Failed to send to {cid}: {e}")
                    failed += 1
        
        return sent, failed

# Start bot
if __name__ == "__main__":
    try:
        bot = BroadcastBot(client)
        logger.info("🚀 Bot started!")
        
        # Schedule periodic cleanup of temporary messages
        async def cleanup_loop():
            while True:
                await temp_manager.cleanup_expired(client)
                await asyncio.sleep(60)  # Check every minute
        
        # Run the bot and cleanup loop
        loop = asyncio.get_event_loop()
        loop.create_task(cleanup_loop())
        
        client.start(bot_token=BOT_TOKEN)
        client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        db_manager.close()