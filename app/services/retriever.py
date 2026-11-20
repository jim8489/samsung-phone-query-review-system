from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.models import Phone
from app.services.catalog import phone_to_document


_SYNONYMS = {
    "screen": "display", "size": "display", "panel": "display",
    "photo": "camera", "photography": "camera", "pictures": "camera", "selfie": "camera",
    "processor": "chipset", "cpu": "chipset", "speed": "performance", "fast": "performance",
    "endurance": "battery", "backup": "battery", "lasting": "battery",
    "memory": "ram", "capacity": "storage", "cost": "price", "pricing": "price",
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(_SYNONYMS.get(token, token))
    return expanded


@dataclass(slots=True)
class RetrievedDocument:
    phone: Phone
    content: str
    score: float


class BM25Retriever:
    """Small, dependency-free BM25 retriever over the live phone catalogue."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def retrieve(self, query: str, phones: list[Phone], top_k: int = 5) -> list[RetrievedDocument]:
        if not phones:
            return []
        docs = [(phone, phone_to_document(phone)) for phone in phones]
        tokenized = [tokenize(text) for _, text in docs]
        query_terms = tokenize(query)
        if not query_terms:
            return [RetrievedDocument(phone, content, 0.0) for phone, content in docs[:top_k]]

        doc_lengths = [len(tokens) for tokens in tokenized]
        avgdl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0
        document_frequency: Counter[str] = Counter()
        for tokens in tokenized:
            document_frequency.update(set(tokens))

        ranked: list[RetrievedDocument] = []
        total_docs = len(docs)
        for (phone, content), tokens, doc_length in zip(docs, tokenized, doc_lengths):
            term_frequency = Counter(tokens)
            score = 0.0
            for term in query_terms:
                frequency = term_frequency.get(term, 0)
                if not frequency:
                    continue
                df = document_frequency[term]
                inverse_frequency = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
                denominator = frequency + self.k1 * (1 - self.b + self.b * doc_length / max(avgdl, 1))
                score += inverse_frequency * (frequency * (self.k1 + 1)) / denominator
            ranked.append(RetrievedDocument(phone=phone, content=content, score=score))
        ranked.sort(key=lambda document: (document.score, document.phone.name), reverse=True)
        return ranked[:top_k]
