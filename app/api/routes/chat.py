from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["Chatbot"])


@router.post("", response_model=ChatResponse, summary="Ask the Samsung phone RAG assistant")
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    return await ChatService(db).ask(payload.query, payload.session_id)
