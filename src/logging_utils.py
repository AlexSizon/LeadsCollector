"""
Pipeline run logger — structured JSONL event logging.

Writes one JSON object per line to ``logs/pipeline_<run_id>.jsonl``.
Four event types are emitted:

* ``run_start``  — once at the beginning of a run
* ``run_end``    — once at the end (always, via try/finally)
* ``query``      — once per city × niche search query
* ``lead``       — once per processed business lead

Usage::

    from src.logging_utils import PipelineLogger, generate_run_id

    run_id = generate_run_id()
    with PipelineLogger(run_id, log_dir=Path("logs")) as logger:
        logger.log_run_start(config)
        ...
        logger.log_query(city, niche, source, len(results), duration_s)
        ...
        logger.log_lead(lead, stages, duration_s)
        ...
        logger.log_run_end(len(leads), total_duration_s)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import BusinessLead


def generate_run_id() -> str:
    """Return a run identifier string in ``YYYYMMDD_HHMMSS`` format (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class PipelineLogger:
    """Append-mode JSONL logger for a single pipeline run.

    Args:
        run_id: Unique identifier for this run (from :func:`generate_run_id`).
        log_dir: Directory where the ``.jsonl`` file will be created.
                 Created automatically if it does not exist.
    """

    def __init__(self, run_id: str, log_dir: Path) -> None:
        self._run_id = run_id
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"pipeline_{run_id}.jsonl"
        self._fh = open(log_path, "a", encoding="utf-8")  # noqa: WPS515

    # ------------------------------------------------------------------
    # Low-level write
    # ------------------------------------------------------------------

    def _write(self, event: dict) -> None:
        self._fh.write(json.dumps(event, default=str) + "\n")
        self._fh.flush()

    # ------------------------------------------------------------------
    # Public event methods
    # ------------------------------------------------------------------

    def log_run_start(self, config: dict) -> None:
        """Emit a ``run_start`` event with top-level run metadata."""
        self._write({
            "event": "run_start",
            "run_id": self._run_id,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "config_cities": config.get("cities", []),
            "config_niches": config.get("niches", []),
            "config_countries": config.get("countries", []),
            "max_results_per_query": config.get("max_results_per_query"),
        })

    def log_run_end(self, total_leads: int, duration_s: float) -> None:
        """Emit a ``run_end`` event with final totals."""
        self._write({
            "event": "run_end",
            "run_id": self._run_id,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "total_leads": total_leads,
            "duration_s": round(duration_s, 3),
        })

    def log_query(
        self,
        city: str,
        niche: str,
        source: str,
        result_count: int,
        duration_s: float,
        *,
        fallback: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Emit a ``query`` event for one city × niche search."""
        self._write({
            "event": "query",
            "run_id": self._run_id,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "city": city,
            "niche": niche,
            "source": source,
            "result_count": result_count,
            "duration_s": round(duration_s, 3),
            "fallback": fallback,
            "error": error,
        })

    def log_lead(self, lead: "BusinessLead", stages: dict, duration_s: float) -> None:
        """Emit a ``lead`` event capturing per-lead processing outcomes.

        Args:
            lead: The fully scored :class:`~src.models.BusinessLead`.
            stages: Dict with boolean/int flags for each enrichment stage:
                ``website_fetched``, ``audit_run``, ``json_ld_found``,
                ``emails_found`` (int), ``social_links_found`` (int),
                ``instagram_handle_found``, ``contact_discovery_run``.
            duration_s: Wall-clock seconds spent processing this lead.
        """
        self._write({
            "event": "lead",
            "run_id": self._run_id,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "company": lead.company_name,
            "city": lead.city,
            "niche": lead.niche,
            "website_status": lead.website_status.value if hasattr(lead.website_status, "value") else str(lead.website_status),
            "score": round(lead.lead_priority_score, 4),
            "tier": lead.tier,
            "duration_s": round(duration_s, 3),
            "stages": stages,
        })

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Flush and close the underlying file handle."""
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self) -> "PipelineLogger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
