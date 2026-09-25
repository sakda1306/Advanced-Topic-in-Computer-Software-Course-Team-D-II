"""Tokens for BM25 and alias matching (from week4 src/hybrid_retriever.py).

English words and numbers are lower-cased; Thai runs are split into words with pythainlp,
because Thai has no spaces between words. Tokens keep their reading order, which alias
matching relies on.
"""

from __future__ import annotations

import re

from pythainlp.tokenize import word_tokenize

_TOKEN = re.compile(r"[A-Za-z0-9]+|[ก-๙]+")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN.finditer(text):
        word = match.group()
        if word[0].isascii():
            tokens.append(word.lower())
        else:
            tokens.extend(t for t in word_tokenize(word, engine="newmm") if t.strip())
    return tokens
