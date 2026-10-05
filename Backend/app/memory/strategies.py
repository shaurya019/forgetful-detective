"""Token-aware conversation truncation.

Three strategies, all sharing two invariants:
  * the system prompt and pinned messages are never dropped;
  * the latest message is never dropped (the model must see what it's answering).

drop_oldest         Evict unprotected messages oldest-first, one at a time,
                    until the context fits the budget. Simple FIFO; can orphan
                    an answer from its question.
system_plus_last_n  Keep the system prompt, pinned messages and the last N other
                    messages. Counts messages, not tokens, so it can overshoot
                    the budget; the result says so in `warnings`.
fit_to_budget       Turn-aware. Groups messages into exchanges (a user message
                    plus the replies after it) and fills the budget newest-first,
                    stopping at the first exchange that doesn't fit so the kept
                    window is contiguous. If even the newest exchange is too big,
                    its overflowing message is trimmed instead of dropped.

The counter is injected so tests can run without downloading tiktoken data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Protocol, Sequence

REPLY_PRIMING_TOKENS = 3
MIN_TRIM_TOKENS = 16


class Counter(Protocol):
    def count_message(self, role: str, content: str) -> int: ...
    def truncate_text(self, text: str, max_tokens: int) -> str: ...


class Strategy(str, Enum):
    DROP_OLDEST = "drop_oldest"
    SYSTEM_PLUS_LAST_N = "system_plus_last_n"
    FIT_TO_BUDGET = "fit_to_budget"


class Status(str, Enum):
    SYSTEM = "system"
    PINNED = "pinned"
    KEPT = "kept"
    TRIMMED = "trimmed"
    DROPPED = "dropped"


@dataclass
class Msg:
    id: str
    role: str  # "system" | "user" | "assistant"
    content: str
    pinned: bool = False


@dataclass
class Decision:
    id: str
    role: str
    status: Status
    tokens: int
    final_tokens: int
    reason: str


@dataclass
class TruncationResult:
    strategy: Strategy
    budget: int
    kept: list[Msg]
    decisions: list[Decision]
    tokens_before: int
    tokens_after: int
    warnings: list[str] = field(default_factory=list)

    @property
    def dropped_ids(self) -> list[str]:
        return [d.id for d in self.decisions if d.status == Status.DROPPED]

    @property
    def trimmed_ids(self) -> list[str]:
        return [d.id for d in self.decisions if d.status == Status.TRIMMED]

    @property
    def under_budget(self) -> bool:
        return self.tokens_after <= self.budget

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "budget": self.budget,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "under_budget": self.under_budget,
            "warnings": self.warnings,
            "decisions": [{**asdict(d), "status": d.status.value} for d in self.decisions],
        }


def truncate(
    messages: Sequence[Msg],
    *,
    strategy: Strategy | str,
    budget: int,
    counter: Counter,
    last_n: int = 8,
) -> TruncationResult:
    strategy = Strategy(strategy)
    msgs = list(messages)
    n = len(msgs)
    last_idx = n - 1
    tokens = [counter.count_message(m.role, m.content) for m in msgs]
    tokens_before = sum(tokens) + REPLY_PRIMING_TOKENS

    status: dict[int, Status] = {}
    reasons: dict[int, str] = {}
    trimmed_content: dict[int, str] = {}
    warnings: list[str] = []

    protected = {i for i, m in enumerate(msgs) if m.role == "system" or m.pinned}
    for i in protected:
        if msgs[i].role == "system":
            status[i], reasons[i] = Status.SYSTEM, "system prompt is always sent"
        else:
            status[i], reasons[i] = Status.PINNED, "pinned, never dropped"

    protected_tokens = sum(tokens[i] for i in protected) + REPLY_PRIMING_TOKENS
    if protected_tokens > budget:
        warnings.append(
            
            f"System prompt and pinned messages need {protected_tokens} tokens, "
            f"more than the {budget}-token budget. Unpin something or raise the budget."
        )

    unprotected = [i for i in range(n) if i not in protected]

    if strategy is Strategy.DROP_OLDEST:
        running = tokens_before
        for i in unprotected:
            if i == last_idx:
                status[i], reasons[i] = Status.KEPT, "latest message is always kept"
            elif running > budget:
                status[i] = Status.DROPPED
                reasons[i] = f"evicted oldest-first (context was {running} of {budget} tokens)"
                running -= tokens[i]
            else:
                status[i], reasons[i] = Status.KEPT, "context already fits"

    elif strategy is Strategy.SYSTEM_PLUS_LAST_N:
        keep = set(unprotected[-last_n:]) if last_n > 0 else set()
        if unprotected and unprotected[-1] == last_idx:
            keep.add(last_idx)
        for i in unprotected:
            if i in keep:
                status[i], reasons[i] = Status.KEPT, f"one of the last {last_n} messages"
            else:
                status[i], reasons[i] = Status.DROPPED, f"older than the last {last_n} messages"

    else:  # FIT_TO_BUDGET
        groups: list[list[int]] = []
        for i in unprotected:
            if msgs[i].role == "user" or not groups:
                groups.append([i])
            else:
                groups[-1].append(i)

        remaining = budget - protected_tokens
        stopped = False
        for gi, group in enumerate(reversed(groups)):
            g_tokens = sum(tokens[i] for i in group)
            if stopped:
                for i in group:
                    status[i], reasons[i] = Status.DROPPED, "older than an exchange that didn't fit"
                continue
            if g_tokens <= remaining:
                for i in group:
                    status[i] = Status.KEPT
                    reasons[i] = f"whole exchange fits ({g_tokens} tokens, {remaining} were free)"
                remaining -= g_tokens
                continue

            stopped = True
            if gi > 0:
                for i in group:
                    status[i] = Status.DROPPED
                    reasons[i] = f"exchange needs {g_tokens} tokens, only {max(remaining, 0)} were free"
                continue

            # The newest exchange doesn't fit: keep it newest-first, trim the message that overflows.
            cut = False
            for i in reversed(group):
                m = msgs[i]
                if cut:
                    status[i], reasons[i] = Status.DROPPED, "older than a message that had to be trimmed"
                elif tokens[i] <= remaining:
                    status[i], reasons[i] = Status.KEPT, "part of the latest exchange"
                    remaining -= tokens[i]
                else:
                    cut = True
                    room = remaining - counter.count_message(m.role, "")
                    if i == last_idx or room >= MIN_TRIM_TOKENS:
                        room = max(room, MIN_TRIM_TOKENS)
                        trimmed_content[i] = counter.truncate_text(m.content, room)
                        new_tokens = counter.count_message(m.role, trimmed_content[i])
                        status[i] = Status.TRIMMED
                        reasons[i] = f"trimmed from {tokens[i]} to {new_tokens} tokens to fit"
                        remaining -= new_tokens
                    else:
                        status[i], reasons[i] = Status.DROPPED, "didn't fit, even trimmed"

    kept: list[Msg] = []
    decisions: list[Decision] = []
    for i, m in enumerate(msgs):
        st = status[i]
        content = trimmed_content.get(i, m.content)
        if st == Status.DROPPED:
            final = 0
        elif i in trimmed_content:
            final = counter.count_message(m.role, content)
        else:
            final = tokens[i]
        decisions.append(Decision(m.id, m.role, st, tokens[i], final, reasons[i]))
        if st != Status.DROPPED:
            kept.append(replace(m, content=content))

    tokens_after = sum(d.final_tokens for d in decisions) + REPLY_PRIMING_TOKENS
    if tokens_after > budget and protected_tokens <= budget:
        if strategy is Strategy.SYSTEM_PLUS_LAST_N:
            warnings.append(
                f"Over budget by {tokens_after - budget} tokens. This strategy counts "
                f"messages, not tokens; lower N or switch to fit_to_budget."
            )
        else:
            warnings.append(
                f"Over budget by {tokens_after - budget} tokens: only protected messages "
                f"and the latest message remain."
            )

    return TruncationResult(strategy, budget, kept, decisions, tokens_before, tokens_after, warnings)
