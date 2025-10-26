from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import re
from telethon import TelegramClient
from telethon.errors import (
    ChatAdminRequiredError,
    MessagePinningRestrictedError,
    FloodWaitError,
    MessageDeleteForbiddenError
)

class RateLimiter:
    def __init__(self, delay: float = 0.5):
        self.delay = delay
        self.last_message_time: Dict[int, datetime] = {}
    
    async def wait_if_needed(self, chat_id: int) -> None:
        if chat_id in self.last_message_time:
            time_diff = datetime.now() - self.last_message_time[chat_id]
            if time_diff.total_seconds() < self.delay:
                await asyncio.sleep(self.delay - time_diff.total_seconds())
        self.last_message_time[chat_id] = datetime.now()

class TempMessageManager:
    def __init__(self):
        self.temp_messages: Dict[int, tuple[int, datetime]] = {}
    
    def add_message(self, msg_id: int, chat_id: int, duration: timedelta) -> None:
        expire_time = datetime.now() + duration
        self.temp_messages[msg_id] = (chat_id, expire_time)
    
    async def cleanup_expired(self, client: TelegramClient) -> None:
        current_time = datetime.now()
        to_delete = []
        
        for msg_id, (chat_id, expire_time) in self.temp_messages.items():
            if current_time >= expire_time:
                try:
                    await client.delete_messages(chat_id, msg_id)
                    to_delete.append(msg_id)
                except (MessageDeleteForbiddenError, Exception) as e:
                    print(f"Failed to delete temporary message {msg_id} in {chat_id}: {e}")
        
        for msg_id in to_delete:
            del self.temp_messages[msg_id]

def parse_duration(time_str: str) -> Optional[timedelta]:
    """Parse duration string in format like '1d2h30m15s'"""
    pattern = r'((?P<days>\d+)d)?((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?'
    match = re.match(pattern, time_str)
    if not match:
        return None
    parts = {name: int(value) for name, value in match.groupdict(default='0').items()}
    return timedelta(**parts)

async def check_admin_permissions(client: TelegramClient, chat_id: int) -> bool:
    """Check if bot has admin permissions in a chat"""
    try:
        participant = await client.get_permissions(chat_id)
        return participant.is_admin
    except Exception as e:
        print(f"Failed to check permissions for {chat_id}: {str(e)}")
        return False

class BatchProcessor:
    @staticmethod
    async def process_chats(chats: list, batch_size: int = 100) -> list:
        """Process chats in batches to prevent memory overload"""
        batches = []
        for i in range(0, len(chats), batch_size):
            batches.append(chats[i:i + batch_size])
        return batches