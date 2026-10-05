"""Replay the scripted interrogation through every truncation strategy.

    python -m scripts.demo_truncation                 # real tiktoken counts
    python -m scripts.demo_truncation --budget 600
    python -m scripts.demo_truncation --fake-tokens   # offline, word counts

For each strategy it prints the context size after every message (proving the
chat stays under budget as it grows) and then the final keep/drop ledger.
"""
import argparse

from app.game.case import build_system_prompt
from app.game.demo_data import DEMO_CASE, DEMO_TRANSCRIPT
from app.memory.strategies import Msg, Status, Strategy, truncate

MARK = {Status.SYSTEM: "SYS", Status.PINNED: "PIN", Status.KEPT: "   ", Status.TRIMMED: "TRM", Status.DROPPED: "---"}
WHO = {"system": "case file", "user": "suspect", "assistant": "detective"}


class WordCounter:
    def count_message(self, role, content):
        return 4 + len(content.split())

    def truncate_text(self, text, max_tokens):
        return " ".join(text.split()[:max_tokens])


def build_messages() -> list[Msg]:
    msgs = [Msg("000001", "system", build_system_prompt(DEMO_CASE))]
    for i, (role, content, pinned, _) in enumerate(DEMO_TRANSCRIPT, start=2):
        msgs.append(Msg(f"{i:06d}", role, content, pinned))
    return msgs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=800)
    ap.add_argument("--last-n", type=int, default=8)
    ap.add_argument("--fake-tokens", action="store_true", help="count words instead of tiktoken tokens")
    args = ap.parse_args()

    if args.fake_tokens:
        counter = WordCounter()
    else:
        from app.memory.tokens import TokenCounter
        counter = TokenCounter("gpt-4o-mini")

    msgs = build_messages()
    for strategy in Strategy:
        print(f"\n=== {strategy.value}  (budget {args.budget}, last_n {args.last_n}) ===")
        print("msg  before -> after   dropped")
        for t in range(2, len(msgs) + 1):
            r = truncate(msgs[:t], strategy=strategy, budget=args.budget, counter=counter, last_n=args.last_n)
            flag = "" if r.under_budget else "  OVER BUDGET"
            print(f"{t:>3}  {r.tokens_before:>6} -> {r.tokens_after:>5}   {len(r.dropped_ids):>3}{flag}")

        print("\nfinal ledger:")
        for d in r.decisions:
            text = next(m.content for m in msgs if m.id == d.id)
            print(f"  {MARK[d.status]} #{int(d.id):<3}{WHO[d.role]:<10}{d.tokens:>4} tok  {text[:56]!r}")
            if d.status in (Status.DROPPED, Status.TRIMMED):
                print(f"{'':>10}why: {d.reason}")
        for w in r.warnings:
            print(f"  warning: {w}")
        tram = next(d for d in r.decisions if d.id == "000007")
        print(f"\n  The 9:30 tram alibi (#7) is {tram.status.value} under {strategy.value}.")


if __name__ == "__main__":
    main()
