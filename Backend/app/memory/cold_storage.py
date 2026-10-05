"""Pinecone "cold storage": where messages go when truncation drops them.

Dropped messages are embedded once and upserted into a per-session namespace.
Each turn, the suspect's latest answer is used as a query, and the closest
archived statements are handed back to the detective as recalled notes. That
is how a forgetful detective can still catch a contradiction from 30 messages ago.
"""
from __future__ import annotations

import logging
import time
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from app.config import Settings

log = logging.getLogger(__name__)

SPEAKER = {"user": "Suspect", "assistant": "Detective"}


def _namespace(session_id: str) -> str:
    return f"session-{session_id}"


class ColdStorage:
    def __init__(self, settings: Settings):
        self.enabled = bool(settings.pinecone_api_key and settings.openai_api_key)
        if not self.enabled:
            log.warning("Pinecone or OpenAI key missing: cold storage disabled, dropped messages are forgotten.")
            return

      

        pc = Pinecone(api_key=settings.pinecone_api_key)
        if settings.pinecone_index not in pc.list_indexes().names():
            pc.create_index(
                name=settings.pinecone_index,
                dimension=settings.embedding_dim,
                metric="cosine",
                spec=ServerlessSpec(cloud=settings.pinecone_cloud, region=settings.pinecone_region),
            )
            while not pc.describe_index(settings.pinecone_index).status["ready"]:
                time.sleep(1)

        embeddings = OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
        self.vectors = PineconeVectorStore(index=pc.Index(settings.pinecone_index), embedding=embeddings)

    def archive(self, session_id: str, messages: list[dict]) -> list[str]:
        """Embed and store messages. Returns the ids that were archived."""
        messages = [m for m in messages if m["role"] in SPEAKER]
        if not self.enabled or not messages:
            return []
        self.vectors.add_texts(
            texts=[f"{SPEAKER[m['role']]}: {m['content']}" for m in messages],
            metadatas=[{"msg_id": m["id"], "role": m["role"], "content": m["content"]} for m in messages],
            ids=[f"{session_id}:{m['id']}" for m in messages],
            namespace=_namespace(session_id),
        )
        return [m["id"] for m in messages]

    def recall(self, session_id: str, query: str, k: int, exclude_ids: set[str]) -> list[dict]:
        """Closest archived messages to `query`, skipping any already in context."""
        if not self.enabled or not query.strip():
            return []
        try:
            hits = self.vectors.similarity_search_with_score(
                query, k=k + len(exclude_ids), namespace=_namespace(session_id)
            )
        except Exception:  # an empty or brand-new namespace is not an error worth failing a turn over
            log.exception("Recall failed")
            return []
        recalled = []
        for doc, score in hits:
            msg_id = doc.metadata.get("msg_id")
            if msg_id and msg_id not in exclude_ids:
                recalled.append({
                    "msg_id": msg_id,
                    "role": doc.metadata.get("role", "user"),
                    "content": doc.metadata.get("content", doc.page_content),
                    "score": round(float(score), 3),
                })
            if len(recalled) == k:
                break
        return recalled
