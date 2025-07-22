from pymongo import MongoClient
from config import MONGO_URL

client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)

db = client.broadcast_bot
try:
    client.server_info()
    print("✅ MongoDB connected successfully.")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
