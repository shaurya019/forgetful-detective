"""A scripted, long interrogation used by the demo seed and the CLI demo.

Message ids start at 1 with the system prompt, so the transcript below runs
from message 2 to message 32.

The trap: in message 7 the suspect says they left at 9:15 for the 9:30 tram.
In message 31 they say they practised until about ten. By then, under the
default 800-token budget, message 7 has been dropped from the detective's
context, so the detective in message 32 misses the contradiction.
Answer "I took the tram home, like I said." and cold-storage recall brings
message 7 back.
"""

DEMO_CASE = {
    "title": "The Halvorsen Violin",
    "crime": (
        "A 1720 violin disappeared from the Halvorsen Conservatory's instrument vault. "
        "The vault was found closed and locked the next morning with the case empty."
    ),
    "location": "Halvorsen Conservatory, east wing",
    "time_window": "Thursday, 9:00 pm to 10:30 pm",
    "suspect_name": "Rin Okafor",
    "suspect_profile": (
        "You are Rin Okafor, a second-year cello student with key-card access to the vault corridor. "
        "Your card is the only student card logged in that corridor on Thursday night."
    ),
    "detective_name": "Inspector Marguerite Vance",
    "detective_style": "Quiet, patient, and fond of letting silences do the work.",
    "evidence": [
        {"item": "Key-card log", "detail": "Rin's card opened the vault corridor door at 9:12 pm."},
        {"item": "Tram 14 camera", "detail": "A rain-soaked passenger boarded at Kessler Street at 9:31 pm; face hidden by a hood."},
        {"item": "Cello case", "detail": "Found in practice room 4 holding a bow that belongs to nobody in the cello section."},
        {"item": "Guard's statement", "detail": "The lights in practice room 4 stayed on until 10:05 pm."},
    ],
}

# (role, content, pinned, suspicion) — suspicion only applies to detective lines
DEMO_TRANSCRIPT: list[tuple[str, str, bool, int | None]] = [
    ("assistant", "Sit down, Ms Okafor. I'm Inspector Vance. The Halvorsen violin left its vault on Thursday night, and your key card was in that corridor at 9:12. Start with when you arrived at the conservatory.", False, 20),
    ("user", "I got there around six for orchestra rehearsal. It ran until about 8:30, then I stayed behind to practise the Elgar for my jury next week.", False, None),
    ("assistant", "Where did you practise, and who saw you?", False, 20),
    ("user", "Practice room 4, like always. Nobody really. Dmitri from the brass section waved through the door window, maybe around quarter to nine.", False, None),
    ("assistant", "Your card opened the vault corridor at 9:12. Why were you there?", False, 25),
    ("user", "The corridor is the shortcut to the side exit. I swiped through on my way out. I left the building at 9:15 and caught the 9:30 tram home.", False, None),
    ("assistant", "The 9:30 tram. Which route, from which stop?", False, 25),
    ("user", "Route 14, from the stop on Kessler Street. It was pouring, so I ran the whole way. I was home before ten and my roommate can confirm it.", False, None),
    ("assistant", "Your roommate's name?", False, 25),
    ("user", "Priya. She was watching a baking show when I came in. She'll remember, because I dripped water all over the hallway and she complained.", False, None),
    ("assistant", "Have you ever handled the Halvorsen violin?", False, 25),
    ("user", "Never. I've never even touched its case. Students can't enter the vault without a faculty escort, and I play cello anyway.", True, None),
    ("assistant", "And yet a cello case turned up in practice room 4 with a bow nobody in your section owns.", False, 35),
    ("user", "People leave things in practice rooms all the time. Six of us share that room. It isn't my case; mine has a lighthouse sticker on the lid.", False, None),
    ("assistant", "Describe the vault corridor as you walked through it.", False, 35),
    ("user", "Dim. The motion lights are slow to come on. I think the vault door was closed, but honestly I wasn't looking. I was thinking about the tram.", False, None),
    ("assistant", "Anyone else in the corridor?", False, 35),
    ("user", "No. Well, I heard the lift, but I didn't see anyone get out of it.", False, None),
    ("assistant", "Tell me about money, Ms Okafor. Tuition here is steep.", False, 35),
    ("user", "I'm on a partial scholarship and I teach two kids on Saturdays. It's tight but I manage. I'm not selling a violin on the black market to pay rent, if that's what you mean.", False, None),
    ("assistant", "Nobody mentioned a black market. Interesting that you did.", False, 45),
    ("user", "Come on. That's obviously what you're implying. Anyone would say it.", False, None),
    ("assistant", "Who knows the vault's code rotation?", False, 45),
    ("user", "Faculty, the two security guards, maybe the librarian. Not students. We only have card access to the corridor, not to the vault itself.", False, None),
    ("assistant", "Back to Thursday. What exactly were you practising?", False, 45),
    ("user", "The first movement of the Elgar concerto, mostly the opening chords. I kept fluffing the shift in bar nine.", False, None),
    ("assistant", "The guard says practice room 4's lights stayed on until 10:05.", False, 50),
    ("user", "That doesn't mean anything. People forget to switch them off constantly.", False, None),
    ("assistant", "Then let's be precise. When did you stop practising?", False, 50),
    ("user", "It must have been close to ten. I lost track of time with the Elgar. I was in room 4 until about ten, then packed up.", False, None),
    ("assistant", "Noted. And once you'd packed up, walk me through getting home.", False, 50),
]
