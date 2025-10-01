# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from db_chat_utility import DBChatUtility
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
db_chat = DBChatUtility()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to ["http://localhost:3000", "https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class QueryRequest(BaseModel):
    user_query: str


@app.post("/query")
def query_db(request: QueryRequest):
    try:
        response = db_chat.run(request.user_query)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}
