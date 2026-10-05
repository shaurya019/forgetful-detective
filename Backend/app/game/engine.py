from __future__ import annotations

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.config import Settings
from app.game.case import CaseFile, DetectiveTurn, build_system_prompt, case_prompt
from app.game.demo_data import DEMO_CASE, DEMO_TRANSCRIPT
from app.memory.cold_storage import SPEAKER, ColdStorage
from app.memory.store import SessionStore
from app.memory.strategies import Msg, Strategy, TruncationResult, truncate
from app.memory.tokens import TokenCounter


class GameError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _to_langchain(messages: list[Msg]) -> list[BaseMessage]:
    kinds = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [kinds[m.role](content=m.content) for m in messages]


class InterrogationEngine:
    def __init__(self, settings: Settings, store: SessionStore, cold: ColdStorage):
        self.settings = settings
        self.store = store
        self.cold = cold
        self.counter = TokenCounter(settings.chat_model)
        self.llm = None
        if settings.openai_api_key:
            from langchain_openai import ChatOpenAI

            self.llm = ChatOpenAI(model=settings.chat_model, api_key=settings.openai_api_key, temperature=0.7)

    # ---- helpers ---------------------------------------------------------

    def _require_llm(self):
        if self.llm is None:
            raise GameError(503, "OPENAI_API_KEY is not set. The demo interrogation works without it; new cases and live turns don't.")
        return self.llm

    def _session(self, session_id: str) -> dict:
        session = self.store.get_session(session_id)
        if not session:
            raise GameError(404, f"No session {session_id}")
        return session

    def default_memory(self) -> dict:
        s = self.settings
        return {"strategy": s.default_strategy, "budget_tokens": s.default_budget_tokens, "last_n": s.default_last_n}

    def _tokens(self, role: str, content: str) -> int:
        return self.counter.count_message(role, content)

    def _truncate(self, messages: list[dict], memory: dict) -> TruncationResult:
        return truncate(
            [Msg(m["id"], m["role"], m["content"], bool(m.get("pinned"))) for m in messages],
            strategy=memory["strategy"],
            budget=int(memory["budget_tokens"]),
            counter=self.counter,
            last_n=int(memory["last_n"]),
        )

    def _recall_note(self, recalled: list[dict]) -> tuple[str | None, list[dict]]:
        """Pack recalled messages into one note, within the recall token budget."""
        lines, used = [], []
        header = "Recalled from your notebook (earlier in this interrogation):"
        for r in recalled:
            line = f'- Message {int(r["msg_id"])}, {SPEAKER.get(r["role"], r["role"])} said: "{r["content"]}"'
            candidate = "\n".join([header, *lines, line])
            if self._tokens("system", candidate) > self.settings.recall_budget_tokens:
                break
            lines.append(line)
            used.append(r)
        return ("\n".join([header, *lines]) if lines else None), used

    # ---- sessions --------------------------------------------------------

    def _open_session(self, case: dict, memory: dict, is_demo: bool) -> dict:
        session = self.store.create_session({
            "title": case["title"],
            "case": case,
            "memory": memory,
            "status": "active",
            "suspicion": 0,
            "player_turns": 0,
            "is_demo": is_demo,
        })
        system = build_system_prompt(case)
        self.store.add_message(session["session_id"], "system", system, self._tokens("system", system))
        return session

    def create_session(self) -> dict:
        llm = self._require_llm()
        case = llm.with_structured_output(CaseFile, method="function_calling").invoke(case_prompt()).model_dump()
        session = self._open_session(case, self.default_memory(), is_demo=False)
        sid = session["session_id"]

        system = build_system_prompt(case)
        opening = llm.with_structured_output(DetectiveTurn, method="function_calling").invoke([
            SystemMessage(content=system),
            SystemMessage(content="The suspect has just sat down. Introduce yourself and ask your first question."),
        ])
        suspicion = max(0, min(100, opening.suspicion))
        self.store.add_message(sid, "assistant", opening.reply, self._tokens("assistant", opening.reply), extra={"suspicion": suspicion})
        return self.store.update_session(sid, suspicion=suspicion)

    def seed_demo(self) -> dict:
        session = self._open_session(DEMO_CASE, self.default_memory(), is_demo=True)
        sid = session["session_id"]
        suspicion, turns = 0, 0
        for role, content, pinned, sus in DEMO_TRANSCRIPT:
            extra = {"suspicion": sus} if sus is not None else None
            self.store.add_message(sid, role, content, self._tokens(role, content), pinned=pinned, extra=extra)
            if sus is not None:
                suspicion = sus
            if role == "user":
                turns += 1
        return self.store.update_session(sid, suspicion=suspicion, player_turns=turns)

    def get(self, session_id: str) -> dict:
        return {"session": self._session(session_id), "messages": self.store.list_messages(session_id)}

    def set_memory(self, session_id: str, memory: dict) -> dict:
        self._session(session_id)
        Strategy(memory["strategy"])  # validates
        return self.store.update_session(session_id, memory=memory)

    def set_pinned(self, session_id: str, msg_id: str, pinned: bool) -> dict:
        self._session(session_id)
        return self.store.set_pinned(session_id, msg_id, pinned)

    def preview(self, session_id: str, overrides: dict) -> dict:
        """What the detective would see right now, without side effects."""
        session = self._session(session_id)
        memory = {**session["memory"], **{k: v for k, v in overrides.items() if v is not None}}
        return self._truncate(self.store.list_messages(session_id), memory).to_dict()

    # ---- a turn ----------------------------------------------------------

    def play_turn(self, session_id: str, content: str) -> dict:
        llm = self._require_llm()
        session = self._session(session_id)
        if session["status"] != "active":
            raise GameError(409, f"This interrogation is over: {session['status']}.")

        user_msg = self.store.add_message(session_id, "user", content, self._tokens("user", content))
        messages = self.store.list_messages(session_id)
        result = self._truncate(messages, session["memory"])

        # Everything newly dropped goes to cold storage, once.
        dropped = set(result.dropped_ids)
        to_archive = [m for m in messages if m["id"] in dropped and not m.get("archived")]
        archived_ids = self.cold.archive(session_id, to_archive)
        self.store.mark_archived(session_id, archived_ids)

        # Recall archived statements that resemble the suspect's answer.
        in_context = {m.id for m in result.kept}
        candidates = self.cold.recall(session_id, content, self.settings.recall_top_k, in_context)
        note, recalled = self._recall_note(candidates)

        prompt = _to_langchain(result.kept)
        if note:
            prompt.insert(len(prompt) - 1, SystemMessage(content=note))  # just before the latest answer

        turn: DetectiveTurn = llm.with_structured_output(DetectiveTurn, method="function_calling").invoke(prompt)
        suspicion = max(0, min(100, turn.suspicion))

        if turn.pin_last_answer:
            self.store.set_pinned(session_id, user_msg["id"], True)

        context = {
            "strategy": result.strategy.value,
            "budget": result.budget,
            "tokens_before": result.tokens_before,
            "tokens_after": result.tokens_after,
            "recall_tokens": self._tokens("system", note) if note else 0,
            "dropped_ids": result.dropped_ids,
            "trimmed_ids": result.trimmed_ids,
            "newly_archived": archived_ids,
            "recalled": [{"msg_id": r["msg_id"], "role": r["role"], "content": r["content"]} for r in recalled],
            "pinned_answer": turn.pin_last_answer,
        }
        assistant_msg = self.store.add_message(
            session_id, "assistant", turn.reply, self._tokens("assistant", turn.reply),
            extra={"suspicion": suspicion, "contradiction": turn.contradiction, "context": context},
        )

        turns = int(session.get("player_turns", 0)) + 1
        status = "arrested" if suspicion >= 100 else "released" if turns >= self.settings.max_player_turns else "active"
        session = self.store.update_session(session_id, suspicion=suspicion, player_turns=turns, status=status)
        return {"session": session, "assistant_message": assistant_msg, "report": result.to_dict(), "recalled": recalled}
