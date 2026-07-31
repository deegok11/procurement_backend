from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from google.genai import errors as genai_errors
from fastapi.responses import JSONResponse

from app.api import (
    routes_auth,
    routes_bill,
    routes_chat,
    routes_documents,
    routes_extraction,
    routes_grn,
    routes_items,
    routes_permissions,
    routes_po,
    routes_pr,
    routes_quotation,
    routes_transaction,
)
from app.auth.middleware import AuthMiddleware
from app.domain.errors import (
    DomainError,
    InvalidTransitionError,
    InvariantViolationError,
    NotAuthorizedError,
    NotFoundError,
    ReasonRequiredError,
)

app = FastAPI(title="Procurement System")

app.add_middleware(AuthMiddleware)

# Added AFTER AuthMiddleware. Starlette's add_middleware() prepends to the
# stack, so the LAST middleware added ends up OUTERMOST — CORS must be
# outermost so it can attach headers to every response, including the 401s
# AuthMiddleware returns directly (without calling call_next) when a token
# is missing/invalid/revoked. When CORS was registered before AuthMiddleware,
# AuthMiddleware ended up outermost instead: it short-circuited straight to a
# JSONResponse for a bad token without ever invoking the inner CORS
# middleware, so those 401s left the server with no
# Access-Control-Allow-Origin header at all. The browser's fetch() can't read
# a cross-origin response missing that header, so response.status is never
# visibly 401 to the frontend — it just looks like a failed network request.
# Verified empirically via curl (see AGENTS.md for the debugging note) rather
# than only reasoning about Starlette's stack-building order. Origins are the
# Vite dev server's default ports; this is a local-dev-only app, so there's
# no separate prod origin list to maintain yet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotAuthorizedError)
def _handle_not_authorized(request: Request, exc: NotAuthorizedError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(NotFoundError)
def _handle_not_found(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidTransitionError)
@app.exception_handler(ReasonRequiredError)
@app.exception_handler(InvariantViolationError)
def _handle_unprocessable(request: Request, exc: DomainError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DomainError)
def _handle_domain_error(request: Request, exc: DomainError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(genai_errors.APIError)
def _handle_gemini_error(request: Request, exc: genai_errors.APIError):
    # The chat/extraction layers call the live Gemini API — a missing/invalid
    # GEMINI_API_KEY, rate limit, or network hiccup should surface as a
    # clean error to the caller, not an opaque 500.
    return JSONResponse(
        status_code=502, content={"detail": f"Gemini API error: {exc.__class__.__name__}: {exc}"}
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(routes_auth.router)
app.include_router(routes_items.router)
app.include_router(routes_pr.router)
app.include_router(routes_quotation.router)
app.include_router(routes_po.router)
app.include_router(routes_grn.router)
app.include_router(routes_bill.router)
app.include_router(routes_transaction.router)
app.include_router(routes_documents.router)
app.include_router(routes_chat.router)
app.include_router(routes_extraction.router)
app.include_router(routes_permissions.router)
