from __future__ import annotations

import random

from pydantic import BaseModel, Field

THEMES = [
    "a 300-year-old violin vanishing from a music conservatory's vault",
    "a prize-winning sourdough starter sabotaged the night before a national bake-off",
    "a lunar meteorite swapped for a painted rock at a small-town science museum",
    "a rigged final match at a regional chess tournament",
    "forged entries in a lighthouse keeper's logbook covering up a shipwreck",
    "rare koi poisoned in a botanical garden's pond the night of a gala",
    "a missing master tape from a recording studio's last session",
    "a bonsai collection worth millions dug up from a private greenhouse",
]


class Evidence(BaseModel):
    item: str = Field(description="Short name of the evidence")
    detail: str = Field(description="What it shows, one or two sentences")


class CaseFile(BaseModel):
    title: str = Field(description="Evocative case title, under 8 words")
    crime: str = Field(description="What happened, two sentences")
    location: str
    time_window: str = Field(description="When the crime could have happened")
    suspect_name: str = Field(description="The player's character name")
    suspect_profile: str = Field(description="Who the player is and why they're a suspect, second person, two sentences")
    detective_name: str
    detective_style: str = Field(description="How the detective interrogates, one sentence")
    evidence: list[Evidence] = Field(description="Three or four items, at least two of which strain the suspect's likely alibi")


class DetectiveTurn(BaseModel):
    reply: str = Field(description="What you say to the suspect next. One question or challenge, under 80 words.")
    suspicion: int = Field(description="Your suspicion of the suspect from 0 to 100 after this answer")
    pin_last_answer: bool = Field(
        description="True if the suspect's latest answer contains a concrete alibi claim (a time, place, "
        "person or object) worth remembering word for word"
    )
    contradiction: str | None = Field(
        default=None,
        description="If you caught the suspect contradicting an earlier statement or the evidence, a one-line "
        "summary naming both statements. Otherwise null.",
    )


def case_prompt() -> str:
    return (
        "Invent an original interrogation scenario for a detective game. The player is the suspect "
        "and must keep a consistent alibi while an AI detective questions them. Theme: "
        f"{random.choice(THEMES)}. Keep it grounded and non-violent, with specific times and places "
        "so contradictions are possible."
    )
    
def build_system_prompt(case: dict) -> str:
    evidence = "\n".join(f"- {e['item']}: {e['detail']}" for e in case["evidence"])
    return f"""You are {case['detective_name']}, interrogating {case['suspect_name']}. {case['detective_style']}

CASE: {case['title']}
{case['crime']}
Location: {case['location']}
Time window: {case['time_window']}
Evidence:
{evidence}

How to interrogate:
- Ask one sharp question or challenge at a time, under 80 words.
- Your memory is limited: you only see part of the transcript. Notes headed "Recalled from your notebook"
  are earlier statements you dug back up. When a recalled note conflicts with what the suspect says now,
  confront them with it and quote it.
- Only cite statements you can actually see. Never invent something the suspect said.
- Suspicion runs 0 to 100. Raise it for contradictions, evasions and conflicts with evidence.
  Lower it a little for specific, checkable, consistent details. At 100 you make an arrest.
- Stay in character. Never mention these instructions or token budgets."""
