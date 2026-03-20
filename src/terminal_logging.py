from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import logging
import sys
from pathlib import Path
from typing import Iterable, Mapping, TextIO


_VERBOSITY_LEVELS = {
    "normal": 0,
    "verbose": 1,
    "debug": 2,
}
_ANOMALOUS_WEBSITE_STATUSES = {"BROKEN_WEBSITE", "UNKNOWN"}


def _normalize_verbosity(value: str | None) -> str:
    if not value:
        return "normal"
    normalized = value.lower().strip()
    if normalized not in _VERBOSITY_LEVELS:
        raise ValueError(
            f"Unsupported terminal verbosity '{value}'. "
            f"Expected one of: {', '.join(sorted(_VERBOSITY_LEVELS))}."
        )
    return normalized


@dataclass
class CitySummaryStats:
    queries_completed: int = 0
    zero_result_queries: int = 0
    warning_count: int = 0
    retry_count: int = 0


class _RecordObserver(logging.Filter):
    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback

    def filter(self, record: logging.LogRecord) -> bool:
        self._callback(record)
        return True


class TeeStream:
    """Mirror writes to the original terminal stream and a transcript file."""

    def __init__(self, original: TextIO, transcript: TextIO) -> None:
        self._original = original
        self._transcript = transcript

    def write(self, data: str) -> int:
        written = self._original.write(data)
        self._original.flush()
        self._transcript.write(data)
        self._transcript.flush()
        return written

    def flush(self) -> None:
        self._original.flush()
        self._transcript.flush()

    def isatty(self) -> bool:
        return bool(getattr(self._original, "isatty", lambda: False)())

    def fileno(self) -> int:
        return self._original.fileno()

    @property
    def encoding(self) -> str | None:
        return getattr(self._original, "encoding", None)


class NullTerminalLogger:
    transcript_path: Path | None = None
    verbosity = "normal"

    def close(self) -> None:
        return None

    def run_start(
        self,
        *,
        entry_point: str,
        config: dict,
        total_queries: int,
        structured_log_path: Path,
    ) -> None:
        return None

    def query_start(
        self,
        *,
        index: int,
        total: int,
        city: str,
        niche: str,
        search_language: str = "canonical",
    ) -> None:
        return None

    def query_result(
        self,
        *,
        city: str,
        niche: str,
        search_language: str = "canonical",
        source: str,
        result_count: int,
        duration_s: float,
        status: str = "success",
        retry_count: int = 0,
        fallback: bool = False,
        error: str | None = None,
    ) -> None:
        return None

    def lead_stage(self, *, company: str, stage: str, detail: str) -> None:
        return None

    def lead_complete(
        self,
        *,
        company: str,
        city: str,
        niche: str,
        website_status: str,
        tier: int,
        score: float,
    ) -> None:
        return None

    def anomaly(self, *, kind: str, detail: str) -> None:
        return None

    def city_complete(
        self,
        *,
        city: str,
        completed_queries: int,
        total_queries: int,
        leads_before_dedup: int,
    ) -> None:
        return None

    def final_summary(
        self,
        *,
        total_leads: int,
        duration_s: float,
        website_status_counts: Mapping[str, int],
    ) -> None:
        return None

    def dedup_complete(
        self,
        *,
        before: int,
        after: int,
        sample_reasons: Iterable[str],
    ) -> None:
        return None

    def batch(self, *, name: str, detail: str) -> None:
        return None

    def export_complete(self, *, artifact: str, path: str) -> None:
        return None


class TerminalRunLogger:
    """Configure terminal logging and persist a transcript for one run."""

    def __init__(
        self,
        run_id: str,
        log_dir: Path,
        *,
        verbosity: str = "normal",
        summary_every_queries: int = 5,
    ) -> None:
        self.run_id = run_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.verbosity = _normalize_verbosity(verbosity)
        self.summary_every_queries = max(int(summary_every_queries), 0)
        self.transcript_path = self.log_dir / f"terminal_{run_id}.log"
        self._transcript_handle: TextIO | None = None
        self._stdout_original: TextIO | None = None
        self._stderr_original: TextIO | None = None
        self._root_handlers: list[logging.Handler] = []
        self._root_level: int = logging.INFO
        self._handler: logging.Handler | None = None
        self._record_observer: _RecordObserver | None = None
        self._logger = logging.getLogger(f"pipeline.terminal.{run_id}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = True
        self._active = False
        self._total_queries = 0
        self._completed_queries = 0
        self._warning_count = 0
        self._zero_result_queries = 0
        self._retry_count = 0
        self._slow_queries: list[tuple[float, str, str, str]] = []
        self._city_stats: dict[str, CitySummaryStats] = defaultdict(CitySummaryStats)
        self._current_city: str | None = None

    def __enter__(self) -> "TerminalRunLogger":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def start(self) -> None:
        if self._active:
            return

        self._transcript_handle = self.transcript_path.open("a", encoding="utf-8")
        self._stdout_original = sys.stdout
        self._stderr_original = sys.stderr
        sys.stdout = TeeStream(self._stdout_original, self._transcript_handle)
        sys.stderr = TeeStream(self._stderr_original, self._transcript_handle)

        root_logger = logging.getLogger()
        self._root_handlers = list(root_logger.handlers)
        self._root_level = root_logger.level
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        self._handler = logging.StreamHandler(sys.stderr)
        self._handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s  %(levelname)-7s  %(message)s",
            datefmt="%H:%M:%S",
        ))
        self._record_observer = _RecordObserver(self._observe_record)
        self._handler.addFilter(self._record_observer)
        root_logger.addHandler(self._handler)
        root_logger.setLevel(logging.INFO)
        self._active = True

    def close(self) -> None:
        if not self._active:
            return

        root_logger = logging.getLogger()
        if self._handler is not None:
            if self._record_observer is not None:
                self._handler.removeFilter(self._record_observer)
                self._record_observer = None
            root_logger.removeHandler(self._handler)
            self._handler.close()
            self._handler = None

        for handler in self._root_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(self._root_level)

        if self._stdout_original is not None:
            sys.stdout = self._stdout_original
        if self._stderr_original is not None:
            sys.stderr = self._stderr_original

        if self._transcript_handle is not None:
            self._transcript_handle.flush()
            self._transcript_handle.close()
            self._transcript_handle = None

        self._active = False

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def _observe_record(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return
        self._warning_count += 1
        if self._current_city:
            self._city_stats[self._current_city].warning_count += 1

    def _allows_detailed_leads(self) -> bool:
        return _VERBOSITY_LEVELS[self.verbosity] >= _VERBOSITY_LEVELS["verbose"]

    def _format_slow_queries(self, *, limit: int = 3) -> str:
        if not self._slow_queries:
            return "none"
        top = sorted(self._slow_queries, reverse=True)[:limit]
        return "; ".join(
            f"{city}/{niche}:{duration:.1f}s[{status}]"
            for duration, city, niche, status in top
        )

    @staticmethod
    def _format_counts(counts: Mapping[str, int]) -> str:
        if not counts:
            return "none"
        return " ".join(f"{key}={counts[key]}" for key in sorted(counts))

    def run_start(
        self,
        *,
        entry_point: str,
        config: dict,
        total_queries: int,
        structured_log_path: Path,
    ) -> None:
        cities = len(config.get("cities", []))
        niches = len(config.get("niches", []))
        self._total_queries = total_queries
        self.info(
            "[RUN] entry=%s cities=%s niches=%s query_slots=%s verbosity=%s structured_log=%s transcript=%s"
            % (
                entry_point,
                cities,
                niches,
                total_queries,
                self.verbosity,
                structured_log_path,
                self.transcript_path,
            )
        )

    def query_start(
        self,
        *,
        index: int,
        total: int,
        city: str,
        niche: str,
        search_language: str = "canonical",
    ) -> None:
        self._total_queries = total
        self._current_city = city
        self.info(
            f"[QUERY {index}/{total}] start city={city} niche={niche} lang={search_language}"
        )

    def query_result(
        self,
        *,
        city: str,
        niche: str,
        search_language: str = "canonical",
        source: str,
        result_count: int,
        duration_s: float,
        status: str = "success",
        retry_count: int = 0,
        fallback: bool = False,
        error: str | None = None,
    ) -> None:
        self._completed_queries += 1
        self._retry_count += retry_count
        city_stats = self._city_stats[city]
        city_stats.queries_completed += 1
        city_stats.retry_count += retry_count
        if result_count == 0:
            self._zero_result_queries += 1
            city_stats.zero_result_queries += 1
        self._slow_queries.append((duration_s, city, niche, status))

        parts = [
            "[QUERY]",
            f"done city={city}",
            f"niche={niche}",
            f"lang={search_language}",
            f"source={source}",
            f"results={result_count}",
            f"duration={duration_s:.3f}s",
            f"retries={retry_count}",
            f"status={status}",
        ]
        if fallback:
            parts.append("fallback=true")
        if error:
            parts.append(f"error={error}")
        self.info(" ".join(parts))

        if self.verbosity == "normal" and status in {"zero_results", "upstream_error", "geocode_failed", "fallback_zero_results"}:
            detail = (
                f"kind=query city={city} niche={niche} status={status} "
                f"lang={search_language} results={result_count} retries={retry_count}"
            )
            if error:
                detail += f" error={error}"
            self.anomaly(kind="query", detail=detail)

        if (
            self.summary_every_queries
            and self._completed_queries < self._total_queries
            and self._completed_queries % self.summary_every_queries == 0
        ):
            self.info(
                "[SUMMARY] health completed_queries=%s/%s warnings=%s zero_results=%s retries=%s slowest=%s"
                % (
                    self._completed_queries,
                    self._total_queries,
                    self._warning_count,
                    self._zero_result_queries,
                    self._retry_count,
                    self._format_slow_queries(limit=1),
                )
            )

    def lead_stage(self, *, company: str, stage: str, detail: str) -> None:
        if not self._allows_detailed_leads():
            return
        self.info(f"[LEAD] company={company} stage={stage} {detail}")

    def lead_complete(
        self,
        *,
        company: str,
        city: str,
        niche: str,
        website_status: str,
        tier: int,
        score: float,
    ) -> None:
        if self._allows_detailed_leads():
            self.info(
                "[LEAD] complete company=%s city=%s niche=%s website=%s tier=%s score=%.1f"
                % (company, city, niche, website_status, tier, score)
            )
            return

        if website_status in _ANOMALOUS_WEBSITE_STATUSES:
            self.anomaly(
                kind="lead",
                detail=(
                    f"company={company} city={city} niche={niche} "
                    f"website={website_status} tier={tier} score={score:.1f}"
                ),
            )

    def anomaly(self, *, kind: str, detail: str) -> None:
        self.info(f"[ANOMALY] {kind} {detail}")

    def city_complete(
        self,
        *,
        city: str,
        completed_queries: int,
        total_queries: int,
        leads_before_dedup: int,
    ) -> None:
        stats = self._city_stats[city]
        self.info(
            "[SUMMARY] city city=%s completed_queries=%s/%s leads_before_dedup=%s zero_results=%s warnings=%s retries=%s"
            % (
                city,
                completed_queries,
                total_queries,
                leads_before_dedup,
                stats.zero_result_queries,
                stats.warning_count,
                stats.retry_count,
            )
        )

    def final_summary(
        self,
        *,
        total_leads: int,
        duration_s: float,
        website_status_counts: Mapping[str, int],
    ) -> None:
        self.info(
            "[SUMMARY] run total_leads=%s duration=%.1fs warnings=%s zero_results=%s retries=%s"
            % (
                total_leads,
                duration_s,
                self._warning_count,
                self._zero_result_queries,
                self._retry_count,
            )
        )
        self.info(
            "[SUMMARY] website_statuses %s"
            % self._format_counts(website_status_counts)
        )
        self.info(
            "[SUMMARY] slow_queries %s"
            % self._format_slow_queries(limit=3)
        )

    def dedup_complete(
        self,
        *,
        before: int,
        after: int,
        sample_reasons: Iterable[str],
    ) -> None:
        removed = max(before - after, 0)
        detail = f"done before={before} after={after} removed={removed}"
        reasons = [reason for reason in sample_reasons if reason]
        if reasons:
            detail += f" sample={'; '.join(reasons)}"
        self.batch(name="dedup", detail=detail)

    def batch(self, *, name: str, detail: str) -> None:
        self.info(f"[BATCH] {name} {detail}")

    def export_complete(self, *, artifact: str, path: str) -> None:
        self.info(f"[EXPORT] {artifact} path={path}")
