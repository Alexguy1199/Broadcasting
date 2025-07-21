import os
import asyncio
from telethon import TelegramClient, events, Button
from database import db
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
DELAY = 0.5  # seconds between each message to avoid flood

client = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

users_collection = db.users
groups_collection = db.groups


@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    if event.is_private:
        users_collection.update_one(
            {"user_id": event.sender_id},
            {"$set": {"user_id": event.sender_id}},
            upsert=True,
        )
        await event.reply("Hey! You're now registered for updates.")
    else:
        groups_collection.update_one(
            {"chat_id": event.chat_id},
            {"$set": {"chat_id": event.chat_id}},
            upsert=True,
        )

# Save group when added
@client.on(events.ChatAction)
async def join_handler(event):
    if event.user_added and event.user_id == (await client.get_me()).id:
        groups_collection.update_one(
            {"chat_id": event.chat_id},
            {"$set": {"chat_id": event.chat_id}},
            upsert=True,
        )


@client.on(events.NewMessage(pattern="/broadcast(pin)?"))
async def broadcast_cmd(event):
    if event.sender_id != OWNER_ID:
        return await event.reply("You're not authorized to use this command.")

    reply = await event.get_reply_message()
    message = event.text.split(None, 1)[1] if " " in event.raw_text else None
    pin = bool(event.pattern_match.group(1))

    if not reply and not message:
        return await event.reply("Send a message or reply to one to broadcast.")

    text = "🟢 Confirm broadcast to all users and groups?"
    buttons = [Button.inline("✅ Confirm", data=f"do_broadcast:{pin}")]
    await event.respond(text, buttons=buttons)


@client.on(events.CallbackQuery(data=lambda d: d.startswith("do_broadcast")))
async def confirm_broadcast(event):
    if event.sender_id != OWNER_ID:
        return await event.answer("Unauthorized", alert=True)

    pin = event.data.decode().split(":")[1] == "True"
    orig_msg = await event.get_message()
    reply = await orig_msg.get_reply_message()
    message_text = orig_msg.text.split(None, 1)[1] if " " in orig_msg.raw_text else None

    targets = list(users_collection.find({})) + list(groups_collection.find({}))
    sent, failed = 0, 0

    progress = await event.edit("📤 Starting broadcast...\n✅ Sent: 0 | ❌ Failed: 0")

    for user in targets:
        try:
            cid = user.get("user_id") or user.get("chat_id")
            if reply:
                sent_msg = await client.send_message(cid, reply)
                if reply.media:
                    await client.send_file(cid, reply.media, caption=reply.text or "")
                else:
                    await client.send_message(cid, reply.text or "")
            elif message_text:
                sent_msg = await client.send_message(cid, message_text)
            else:
                continue

            if pin:
                await client.pin_message(cid, sent_msg.id, notify=False)

            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(DELAY)
        await progress.edit(f"📤 Broadcasting...\n✅ Sent: {sent} | ❌ Failed: {failed}")

    await progress.edit(f"✅ Broadcast Complete!\n✅ Sent: {sent}\n❌ Failed: {failed}")


@client.on(events.NewMessage(pattern="/stats"))
async def stats_handler(event):
    if event.sender_id != OWNER_ID:
        return

    total_users = users_collection.count_documents({})
    total_groups = groups_collection.count_documents({"chat_id": {"$lt": 0}})
    total_channels = groups_collection.count_documents({"chat_id": {"$gt": 0}})

    admin_groups = 0
    admin_channels = 0

    for chat in groups_collection.find({}):
        cid = chat["chat_id"]
        try:
            admins = await client.get_participants(cid, filter=types.ChannelParticipantsAdmins)
            if any(admin.id == (await client.get_me()).id for admin in admins):
                if cid < 0:
                    admin_groups += 1
                else:
                    admin_channels += 1
        except Exception:
            continue

    await event.reply(
        f"📊 Bot Stats:\n"
        f"👤 Users: {total_users}\n"
        f"👥 Groups: {total_groups} | Admin in: {admin_groups}\n"
        f"📢 Channels: {total_channels} | Admin in: {admin_channels}"
    )

print("🤖 Bot is now running...")
client.run_until_disconnected()
