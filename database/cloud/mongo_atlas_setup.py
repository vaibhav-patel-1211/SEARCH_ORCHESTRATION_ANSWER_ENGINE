from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(
  os.getenv('MONGO_URI'),
  tls=True,
  tlsCAFile=certifi.where()
)

# create database
db = client["rag_db"]
documents = db["documents"]
uploaded_document_chunks = db["uploaded_document_chunks"]
