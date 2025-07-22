import os
import re
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, types
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID, DEFAULT_DELAY
from database import db

client = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
users = db.users
groups = db.groups


@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    if event.is_private:
        users.update_one({"user_id": event.sender_id}, {"$set": {"user_id": event.sender_id}}, upsert=True)
        await event.reply("Hello! I'm alive and ready. 🤖")
    else:
        groups.update_one({"chat_id": event.chat_id}, {"$set": {"chat_id": event.chat_id}}, upsert=True)

@client.on(events.ChatAction)
async def join_handler(event):
    if event.user_added and event.user_id == (await client.get_me()).id:
        groups.update_one({"chat_id": event.chat_id}, {"$set": {"chat_id": event.chat_id}}, upsert=True)


@client.on(events.NewMessage(pattern="/broadcast"))
async def broadcast_command(event):
    if event.sender_id != OWNER_ID:
        return

    reply = await event.get_reply_message()
    args = event.raw_text.split(None, 1)
    msg = args[1] if len(args) > 1 else None
    pin = bool(event.pattern_match.group(1))

    if not msg and not reply:
        return await event.reply("Reply to a message or provide text to broadcast.")

    content = reply or msg
    await event.respond(
        "📢 Select broadcast option:",
        buttons=[
            [Button.inline("✅ Confirm Broadcast", f"confirm:{pin}:noforward"),
             Button.inline("📌 Broadcast + Pin", f"confirm:{True}:noforward")],
            [Button.inline("❌ Cancel", b"cancel")]
        ]
    )


@client.on(events.NewMessage(incoming=True))
async def auto_broadcast_buttons(event):
    if event.sender_id != OWNER_ID or not event.is_private:
        return

    if event.raw_text and event.raw_text.startswith("/"):
        return

    await event.reply(
        "📝 Do you want to broadcast this message?",
        buttons=[
            [Button.inline("✅ Confirm Broadcast", f"confirm:{False}:noforward"),
             Button.inline("📌 Broadcast + Pin", f"confirm:{True}:noforward")],
            [Button.inline("❌ Cancel", b"cancel")]
        ]
    )


def parse_duration(time_str):
    pattern = r'((?P<days>\d+)d)?((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?'
    match = re.match(pattern, time_str)
    if not match:
        return None
    parts = {name: int(value) for name, value in match.groupdict(default='0').items()}
    return timedelta(**parts)


@client.on(events.CallbackQuery(data=lambda d: d.startswith(b"confirm")))
async def confirm_broadcast(event):
    if event.sender_id != OWNER_ID:
        return await event.answer("You're not authorized.", alert=True)

    _, pin, _ = event.data.decode().split(":")
    pin = pin == "True"
    reply = await event.get_message().get_reply_message()

    await event.edit(
        "🛠 Choose delivery method:",
        buttons=[
            [Button.inline("📨 With Forward Tag", f"send:{pin}:forward"),
             Button.inline("✉️ Without Forward Tag", f"send:{pin}:noforward")],
            [Button.inline("⏳ Temporary Broadcast", f"temp:{pin}")],
            [Button.inline("❌ Cancel", b"cancel")]
        ]
    )

@client.on(events.CallbackQuery(data=b"cancel"))
async def cancel_broadcast(event):
    if event.sender_id == OWNER_ID:
        await event.edit("❌ Broadcast canceled.")


@client.on(events.CallbackQuery(data=lambda d: d.startswith(b"send")))
async def send_broadcast(event):
    if event.sender_id != OWNER_ID:
        return

    _, pin, method = event.data.decode().split(":")
    pin = pin == "True"
    forward = method == "forward"
    reply = await event.get_message().get_reply_message()
    message = reply or await event.get_message()

    target_chats = list(users.find({})) + list(groups.find({}))
    sent, failed = 0, 0
    progress = await event.edit("📤 Starting broadcast...")

    for chat in target_chats:
        cid = chat.get("user_id") or chat.get("chat_id")
        try:
            if forward:
                sent_msg = await client.forward_messages(cid, message)
            else:
                if message.media:
                    sent_msg = await client.send_file(cid, file=message.media, caption=message.text or "")
                else:
                    sent_msg = await client.send_message(cid, message.text or "")
            if pin:
                await client.pin_message(cid, sent_msg.id, notify=False)
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(DEFAULT_DELAY)
        await progress.edit(f"📤 Broadcasting...\n✅ Sent: {sent} | ❌ Failed: {failed}")

    await progress.edit(f"✅ Done!\n✅ Sent: {sent} | ❌ Failed: {failed}")


@client.on(events.CallbackQuery(data=lambda d: d.startswith(b"temp")))
async def temp_options(event):
    if event.sender_id != OWNER_ID:
        return

    _, pin = event.data.decode().split(":")
    await event.edit(
        "🕒 Choose time for auto-delete:",
        buttons=[
            [Button.inline("1 Hour", f"tempdur:{pin}:1h"),
             Button.inline("30 Minutes", f"tempdur:{pin}:30m")],
            [Button.inline("⏱ Custom", f"tempdur:{pin}:custom"),
             Button.inline("❌ Cancel", b"cancel")]
        ]
    )

@client.on(events.CallbackQuery(data=lambda d: d.startswith(b"tempdur")))
async def temp_duration(event):
    if event.sender_id != OWNER_ID:
        return

    _, pin, dur = event.data.decode().split(":")
    pin = pin == "True"
    reply = await event.get_message().get_reply_message()

    if dur == "custom":
        return await event.edit("📝 Send duration like `1d2h30m15s` in next message.")

    delay = parse_duration(dur)
    if not delay:
        return await event.edit("❌ Invalid time format.")

    await send_temp_broadcast(event, reply or await event.get_message(), pin, delay)


@client.on(events.NewMessage(from_users=OWNER_ID, pattern=r"^\d+[dhms]"))
async def custom_time_broadcast(event):
    if not event.is_private:
        return

    reply = await event.get_reply_message()
    dur = parse_duration(event.raw_text)
    if not dur:
        return await event.reply("❌ Invalid time format.")

    await send_temp_broadcast(event, reply or event, pin=False, duration=dur)


async def send_temp_broadcast(event, message, pin, duration):
    chats = list(users.find({})) + list(groups.find({}))
    sent, failed = 0, 0
    progress = await event.respond(f"📤 Sending temporary broadcast...")

    for chat in chats:
        cid = chat.get("user_id") or chat.get("chat_id")
        try:
            if message.media:
                sent_msg = await client.send_file(cid, message.media, caption=message.text or "")
            else:
                sent_msg = await client.send_message(cid, message.text or "")

            if pin:
                await client.pin_message(cid, sent_msg.id, notify=False)

            await asyncio.sleep(duration.total_seconds())
            await client.delete_messages(cid, sent_msg.id)
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(DEFAULT_DELAY)
        await progress.edit(f"⏳ Temporary Broadcast...\n✅ Sent: {sent} | ❌ Failed: {failed}")

    await progress.edit(f"✅ Temporary Broadcast Done!\n✅ Sent: {sent} | ❌ Failed: {failed}")


@client.on(events.NewMessage(pattern="/stats"))
async def stats(event):
    if event.sender_id != OWNER_ID:
        return

    total_users = users.count_documents({})
    total_groups = groups.count_documents({"chat_id": {"$lt": 0}})
    total_channels = groups.count_documents({"chat_id": {"$gt": 0}})

    admin_groups = 0
    admin_channels = 0

    for chat in groups.find({}):
        cid = chat["chat_id"]
        try:
            admins = await client.get_participants(cid, filter=types.ChannelParticipantsAdmins)
            if any(admin.id == (await client.get_me()).id for admin in admins):
                if cid < 0:
                    admin_groups += 1
                else:
                    admin_channels += 1
        except:
            continue

    await event.reply(
        f"📊 Stats:\n"
        f"👤 Users: {total_users}\n"
        f"👥 Groups: {total_groups} (Admin in {admin_groups})\n"
        f"📢 Channels: {total_channels} (Admin in {admin_channels})"
    )

print("🚀 Bot started!")
client.run_until_disconnected()
