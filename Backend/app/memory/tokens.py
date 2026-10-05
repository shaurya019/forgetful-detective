"""Token counting with tiktoken.

Follows OpenAI's chat-format accounting for gpt-4o-family models: every message
costs its content tokens + its role tokens + 3 tokens of framing, and every
request pays 3 more tokens to prime the assistant's reply.
"""
from functools import lru_cache

import tiktoken

TOKENS_PER_MESSAGE = 3
TRIM_MARKER = " …[trimmed]… "

# tiktoken.encoding_for_model(model) looks up the tokenizer that a given OpenAI model uses and returns it as an Encoding object. For example, "gpt-4o" maps to the o200k_base encoding, while "gpt-4" maps to cl100k_base.
# What it's for: different models split text into tokens differently, so to count tokens accurately you need the same tokenizer the model itself uses. The returned object is what turns text into token IDs (.encode()) and back (.decode()).

@lru_cache(maxsize=8)
def _encoding(model: str) -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("o200k_base")
    
class TokenCounter:
    def __init__(self,model):
        self.model = model
        self.enc = _encoding(model)
        
    def count_text(self, text: str) -> int:
        return len(self.enc.encode(text))

    def count_message(self, role: str, content: str) -> int:
        return TOKENS_PER_MESSAGE + self.count_text(role) + self.count_text(content)
    
    def truncate_text(self, text: str, max_tokens: int) -> str:
        """Shorten text to at most max_tokens, keeping its head and tail."""
        ids = self.enc.encode(text)
        if len(ids) <= max_tokens:
            return text
        room = max(max_tokens - self.count_text(TRIM_MARKER),0)
        head = room // 2
        tail = room - head
        tail_text = self.enc.decode(ids[-tail:]) if tail else ""
        return self.enc.decode(ids[:head]) + TRIM_MARKER + tail_text