from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.game.engine import GameError, InterrogationEngine
from app.memory.cold_storage import ColdStorage
from app.memory.store import SessionStore

StrategyName = Literal["drop_oldest", "system_plus_last_n", "fit_to_budget"]


class MemoryConfig(BaseModel):
    strategy: StrategyName
    budget_tokens: int = Field(ge=200, le=128_000)
    last_n: int = Field(ge=0, le=200)


class Answer(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class PinUpdate(BaseModel):
    pinned: bool


@lru_cache
def get_engine() -> InterrogationEngine:
    settings = get_settings()
    return InterrogationEngine(settings, SessionStore(settings), ColdStorage(settings))


settings = get_settings()
app = FastAPI(title="Alibi", description="Interrogation game with a token-budgeted detective memory")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GameError)
def game_error(_: Request, exc: GameError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


api = APIRouter(prefix="/api")


@api.get("/health")
def health(engine: InterrogationEngine = Depends(get_engine)):
    return {
        "openai": engine.llm is not None,
        "cold_storage": engine.cold.enabled,
        "table": engine.store.table_name,
        "model": engine.settings.chat_model,
        "defaults": engine.default_memory(),
    }


@api.get("/sessions")
def list_sessions(engine: InterrogationEngine = Depends(get_engine)):
    return engine.store.list_sessions()


@api.post("/sessions", status_code=201)
def create_session(engine: InterrogationEngine = Depends(get_engine)):
    return engine.create_session()


@api.post("/demo/seed", status_code=201)
def seed_demo(engine: InterrogationEngine = Depends(get_engine)):
    return engine.seed_demo()


@api.get("/sessions/{session_id}")
def get_session(session_id: str, engine: InterrogationEngine = Depends(get_engine)):
    return engine.get(session_id)


@api.post("/sessions/{session_id}/messages")
def answer(session_id: str, body: Answer, engine: InterrogationEngine = Depends(get_engine)):
    return engine.play_turn(session_id, body.content.strip())


@api.patch("/sessions/{session_id}/messages/{msg_id}")
def pin(session_id: str, msg_id: str, body: PinUpdate, engine: InterrogationEngine = Depends(get_engine)):
    return engine.set_pinned(session_id, msg_id, body.pinned)


@api.put("/sessions/{session_id}/memory")
def set_memory(session_id: str, body: MemoryConfig, engine: InterrogationEngine = Depends(get_engine)):
    return engine.set_memory(session_id, body.model_dump())


@api.get("/sessions/{session_id}/context")
def preview_context(
    session_id: str,
    strategy: StrategyName | None = None,
    budget_tokens: int | None = None,
    last_n: int | None = None,
    engine: InterrogationEngine = Depends(get_engine),
):
    return engine.preview(session_id, {"strategy": strategy, "budget_tokens": budget_tokens, "last_n": last_n})


app.include_router(api)
