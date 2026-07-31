from contextvars import ContextVar

from app.domain.schemas import CurrentUser

# Gemini's automatic function calling derives each tool's schema from the
# Python function signature, so current_user can never be a normal tool
# parameter — the model must never supply identity. Set once per chat turn
# (app/ai/chat_agent.py), read inside every tool body. This is how P2 (the
# LLM is never in the authorization path) is wired end to end: tools read
# the REAL caller from here and pass it straight into the same service
# functions the REST routes call.
current_user_ctx: ContextVar[CurrentUser] = ContextVar("current_user_ctx")
