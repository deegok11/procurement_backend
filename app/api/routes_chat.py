from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.ai.chat_agent import ChatTurnResult, run_chat_turn
from app.api.deps import get_current_user
from app.domain.permissions import require_permission
from app.domain.schemas import CurrentUser

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionResponse(BaseModel):
    session_id: str


class SendMessageRequest(BaseModel):
    message: str


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(current_user: CurrentUser = Depends(get_current_user)) -> CreateSessionResponse:
    require_permission(current_user, "chat:use")
    return CreateSessionResponse(session_id=uuid4().hex)


@router.post("/sessions/{session_id}/messages", response_model=ChatTurnResult)
def send_message(
    session_id: str, body: SendMessageRequest, current_user: CurrentUser = Depends(get_current_user)
) -> ChatTurnResult:
    require_permission(current_user, "chat:use")
    return run_chat_turn(session_id, current_user, body.message)
