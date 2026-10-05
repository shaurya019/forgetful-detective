# Alibi

An interrogation game where **you are the suspect** and an AI detective questions you. The twist: the detective's
memory is a real, token-budgeted context window. Whatever falls out of it, you get away with, unless something you
say makes the detective dig it back out of cold storage.

Most LLM detective games put you in the detective's chair. Alibi flips that, and turns conversation-history
truncation into the core mechanic: the truncation strategy and token budget are effectively the difficulty setting,
and you can watch, line by line, what the detective has forgotten.

## What the memory system does

| Requirement | Where |
|---|---|
| Messages stored per session in DynamoDB | `backend/app/memory/store.py` (single table, `pk=SESSION#id`, `sk=META` or `MSG#000123`) |
| Token counting with tiktoken | `backend/app/memory/tokens.py` (OpenAI chat-format accounting: content + role + 3 per message, + 3 reply priming) |
| Drop oldest | `strategies.py`, `drop_oldest`: FIFO eviction until under budget |
| Keep system prompt plus last N | `strategies.py`, `system_plus_last_n`: count-based, warns when it overshoots tokens |
| Fit to a token budget | `strategies.py`, `fit_to_budget`: keeps whole Q/A exchanges newest-first, contiguous window, trims the latest message if it alone overflows |
| Pinned messages never drop | All strategies. The user pins lines in the UI, and the **detective pins** answers it judges to be key alibi claims (structured output field `pin_last_answer`) |
| Demo: long chat under budget, showing drops | Seeded demo interrogation + live memory panel + `scripts/demo_truncation.py` |

Beyond the brief: dropped messages are embedded once and archived to **Pinecone** (namespace per session). Every turn,
the suspect's answer is used as a query, and the closest archived lines are injected as "Recalled from your
notebook" within a separate recall budget. That's how a forgetful detective can still catch a contradiction from 30
lines ago.

```
 answer ──► DynamoDB ──► truncate(strategy, budget, pins) ──► kept window ──┐
                                   │                                         │
                                   └─ newly dropped ──► Pinecone (archive)   ├──► ChatOpenAI (LangChain,
                                                            │                │    structured DetectiveTurn)
                     answer as query ──► Pinecone recall ───┴──► recall note ┘          │
                                                                                         ▼
                                    reply, suspicion, pin_last_answer, contradiction ──► DynamoDB
```

## Stack

Backend: FastAPI, LangChain (`langchain-openai`, `langchain-pinecone`), OpenAI, tiktoken, AWS DynamoDB (boto3), Pinecone.
Frontend: React 19, Tailwind CSS v4, TanStack Query v5, Vite.

## Run it

You need Python 3.11+, Node 20+, and Docker (only for local DynamoDB).

```bash
# 1. DynamoDB Local on :8001  (or skip and point at real AWS, see .env.example)
docker compose up -d dynamodb

# 2. Backend on :8000
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY, optionally PINECONE_API_KEY
uvicorn app.main:app --reload

# 3. Frontend on :5173 (proxies /api to :8000)
cd ../frontend
npm install
npm run dev
```

The table is created on first request (`AUTO_CREATE_TABLE=true`) and the Pinecone index the same way if missing
(serverless, 1536 dims, cosine).

Without an OpenAI key, the demo interrogation still loads and the memory panel works fully; only new cases and live
answers are disabled. Without Pinecone, forgotten lines are simply gone.

## The demo

Click **Load the demo interrogation**. It seeds a 31-line interview about a stolen 1720 violin.

1. Look at the transcript. Under the default `fit_to_budget` at 800 tokens, the early lines are struck through in
   red. Line 7, where the suspect says *"I left the building at 9:15 and caught the 9:30 tram home"*, is forgotten.
   Line 13 is highlighted: the detective pinned that denial, so it never drops.
2. Line 31 contradicts line 7 (*"I was in room 4 until about ten"*). The detective's reply on line 32 misses it,
   because line 7 was outside its memory.
3. Drag the budget slider and switch strategies. The transcript and the ledger update live, with the reason each
   line was kept or dropped, while the budget bar shows the context staying under the line.
4. Answer: `I took the tram home, like I said.` Line 7 gets archived to Pinecone, recalled by similarity, and handed
   back to the detective, who can now confront you with it. The memory panel shows what was pulled from cold storage.

Or from the terminal, no services needed:

```bash
cd backend
python -m scripts.demo_truncation                  # real tiktoken counts, budget 800
python -m scripts.demo_truncation --budget 600 --last-n 6
```

It replays the transcript one message at a time through each strategy, printing tokens before and after truncation
at every step (it stays under budget as the chat grows) and a final ledger with the reason for each drop.

## Tests

```bash
cd backend && pytest
```

15 tests: strategy invariants (budget respected at every turn of the long demo, system/pinned/latest always
survive, FIFO order, whole exchanges kept, oversized-message trimming, pinned-overflow warning) and API flows
against moto-mocked DynamoDB with a stub LLM, including the archive-and-recall path. They use an injected
approximate counter, so they run offline.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/health` | Which services are configured |
| GET | `/api/sessions` | Case list |
| POST | `/api/sessions` | Generate a new case (LLM) |
| POST | `/api/demo/seed` | Seed the scripted demo (no LLM) |
| GET | `/api/sessions/{id}` | Session + messages |
| POST | `/api/sessions/{id}/messages` | Answer; returns the detective's turn and the truncation report |
| PATCH | `/api/sessions/{id}/messages/{msg_id}` | Pin or unpin |
| PUT | `/api/sessions/{id}/memory` | Save strategy, budget, last N |
| GET | `/api/sessions/{id}/context` | Dry-run truncation with optional overrides (powers the live preview) |

## Layout

```
backend/
  app/
    main.py                 FastAPI routes
    config.py               settings (.env)
    memory/
      tokens.py             tiktoken counter
      strategies.py         the three strategies + pinning, pure functions
      store.py              DynamoDB
      cold_storage.py       Pinecone archive + recall (LangChain)
    game/
      case.py               case file + DetectiveTurn schemas, system prompt
      engine.py             one turn: truncate, archive, recall, call the model
      demo_data.py          scripted long interrogation
  scripts/demo_truncation.py
  tests/
frontend/
  src/
    hooks/queries.js        TanStack Query: queries, optimistic answer + pin
    components/
      Transcript.jsx        Q./A. transcript, struck lines, highlighter pins
      MemoryPanel.jsx       strategy controls, budget bar, recall, ledger
```

## Ideas for next steps

Summarise dropped exchanges into a rolling "case notes" message instead of only archiving them; add a GSI on
`created_at` instead of scanning for the case list; stream detective replies; add a hard mode where the suspect
can't see the memory panel.
