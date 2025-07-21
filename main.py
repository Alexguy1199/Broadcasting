from telethon import TelegramClient, events, types
from database import db
import asyncio
import os

# Bot credentials
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

users_collection = db.users
groups_collection = db.groups


@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    if event.is_private:
        users_collection.update_one(
            {"user_id": event.sender_id},
            {"$set": {"user_id": event.sender_id}},
            upsert=True
        )
        await event.respond("Hello!.")
    else:
        groups_collection.update_one(
            {"chat_id": event.chat_id},
            {"$set": {"chat_id": event.chat_id}},
            upsert=True
        )


@client.on(events.ChatAction)
async def added_to_group(event):
    if event.user_added and event.user_id == (await client.get_me()).id:
        groups_collection.update_one(
            {"chat_id": event.chat_id},
            {"$set": {"chat_id": event.chat_id}},
            upsert=True
        )

@client.on(events.NewMessage(pattern="/broadcast(?:pin)?"))
async def broadcast_handler(event):
    if event.sender_id != (await client.get_me()).id:
        return

    pin_msg = event.pattern_match.group(0) == "/broadcastpin"

    
    reply = await event.get_reply_message()
    msg_text = event.text.split(" ", maxsplit=1)[1] if " " in event.raw_text else None

    
    chats = list(users_collection.find({})) + list(groups_collection.find({}))
    success, fail = 0, 0

    for chat in chats:
        try:
            cid = chat.get("user_id") or chat.get("chat_id")
            if reply:
                sent = await client.send_message(cid, reply)
                if reply.media:
                    await client.send_file(cid, reply.media, caption=reply.text or "")
                elif reply.document:
                    await client.send_file(cid, reply.document, caption=reply.text or "")
                else:
                    await client.send_message(cid, reply.text or "")
            elif msg_text:
                sent = await client.send_message(cid, msg_text)
            else:
                continue

            if pin_msg:
                await client.pin_message(cid, sent.id, notify=False)
            success += 1
        except Exception as e:
            fail += 1
            continue

    await event.reply(f"Broadcast complete.\n✅ Success: {success}\n❌ Failed: {fail}")

print("Bot is running...")
client.run_until_disconnected()
