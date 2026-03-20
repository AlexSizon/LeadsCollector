"""Helpers for multilingual niche search phrases."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple


_NICHES_PATH = Path(__file__).resolve().parent.parent / "config" / "niches.json"
_DEFAULT_SEARCH_LANGUAGE = "canonical"


@lru_cache(maxsize=1)
def _load_localized_search_labels() -> dict[str, dict[str, str]]:
    try:
        with open(_NICHES_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    labels = data.get("localized_search_labels", {})
    return labels if isinstance(labels, dict) else {}


def get_search_languages(config: dict) -> List[str]:
    """Return normalized search languages from config, or empty for canonical search."""
    raw = config.get("search_languages")
    if not raw:
        return []

    normalized: List[str] = []
    seen: set[str] = set()
    for value in raw:
        lang = str(value).strip().lower()
        if not lang or lang in seen:
            continue
        seen.add(lang)
        normalized.append(lang)
    return normalized


def resolve_search_label(canonical_niche: str, search_language: str | None) -> str:
    """Resolve a localized search phrase for a canonical niche."""
    canonical = str(canonical_niche).strip()
    if not canonical:
        return canonical
    if not search_language or search_language == _DEFAULT_SEARCH_LANGUAGE:
        return canonical

    localized = _load_localized_search_labels().get(canonical, {})
    value = localized.get(search_language)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return canonical


def build_search_variants(canonical_niche: str, search_languages: List[str]) -> List[Tuple[str, str]]:
    """Return (search_language, search_label) variants for a canonical niche."""
    if not search_languages:
        return [(_DEFAULT_SEARCH_LANGUAGE, canonical_niche)]
    return [
        (language, resolve_search_label(canonical_niche, language))
        for language in search_languages
    ]
