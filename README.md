# Broadcast Bot

A powerful broadcast bot using [Telethon](https://github.com/LonamiWebs/Telethon) and MongoDB with full media support, confirmation buttons, progress updates, and statistics.

---

## 🔧 Features

- Broadcast message or media via `/broadcast` (reply or direct text)
- Optional pinning with `/broadcastpin`
- Inline confirmation before sending
- Live progress report
- User and group tracking (auto-save)
- `/stats` command to view:
  - Total groups and channels
  - Admin presence status
  - Users who started the bot

---

## 📦 Environment Variables

| Variable     | Description                         |
|--------------|-------------------------------------|
| `API_ID`     | Telegram API ID                     |
| `API_HASH`   | Telegram API Hash                   |
| `BOT_TOKEN`  | Bot token from @BotFather           |
| `MONGO_URL`  | MongoDB connection URI              |
| `OWNER_ID`   | Your Telegram user ID               |
| `DELAY`      | Delay between messages (default 0.5)|

---

## 🐳 Docker Deployment

```bash
# Build image
docker build -t telethon-bot .

# Run container
docker run -e API_ID= -e API_HASH= -e BOT_TOKEN= -e MONGO_URL= -e OWNER_ID= telethon-bot
