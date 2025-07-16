import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME")

if not (MONGODB_URI and MONGO_DB_NAME and MONGO_COLLECTION_NAME):
    raise ValueError("MONGODB_URI, MONGO_DB_NAME, and MONGO_COLLECTION_NAME must be set in .env")

client = MongoClient(MONGODB_URI)
db = client[MONGO_DB_NAME]
collection = db[MONGO_COLLECTION_NAME]

def get_mongo_collection():
    return collection

def log_candidate_response(name, phone, transcript, decision):
    print({
        "name": name,
        "phone": phone,
        "transcript": transcript,
        "decision": decision
    })