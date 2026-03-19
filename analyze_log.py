#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"


def resolve_log_path(path_arg: str | None) -> Path:
    if path_arg:
        return Path(path_arg).expanduser().resolve()

    candidates = sorted(LOG_DIR.glob("pipeline_*.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No pipeline log files found in {LOG_DIR}")
    return candidates[-1]


def load_events(log_path: Path) -> list[dict]:
    events: list[dict] = []
    with log_path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                print(
                    f"Warning: skipped malformed JSON on line {line_no}: {exc}",
                    file=sys.stderr,
                )
                continue
            if isinstance(event, dict):
                events.append(event)
            else:
                print(
                    f"Warning: skipped non-object JSON on line {line_no}",
                    file=sys.stderr,
                )
    return events


def format_duration(duration_s: float | int | None) -> str:
    if duration_s is None:
        return "unknown"
    total_minutes = int(float(duration_s) // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


def print_table(headers: list[str], rows: Iterable[Iterable[object]]) -> None:
    rows = [[str(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def _render(values: list[str]) -> str:
        return " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(values))

    print(_render(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(_render(row))


def print_run_summary(events: list[dict]) -> None:
    run_start = next((event for event in events if event.get("event") == "run_start"), None)
    run_end = next((event for event in reversed(events) if event.get("event") == "run_end"), None)

    print("## Run Summary")
    if run_start is None and run_end is None:
        print("No run metadata found.")
        print()
        return

    run_id = (run_start or run_end or {}).get("run_id", "unknown")
    started_at = (run_start or {}).get("ts", "unknown")
    duration_s = (run_end or {}).get("duration_s")
    total_leads = (run_end or {}).get("total_leads", 0)
    city_count = len((run_start or {}).get("config_cities", []))
    niche_count = len((run_start or {}).get("config_niches", []))

    print(f"run_id: {run_id}")
    print(f"start: {started_at}")
    print(f"duration: {format_duration(duration_s)}")
    print(f"total_leads: {total_leads}")
    print(f"cities: {city_count}")
    print(f"niches: {niche_count}")
    print()


def print_query_coverage(events: list[dict]) -> None:
    queries = [event for event in events if event.get("event") == "query"]

    print("## Query Coverage")
    if not queries:
        print("No query events found.")
        print()
        return

    zero_results = [
        [
            event.get("city", ""),
            event.get("niche", ""),
            event.get("source", ""),
            event.get("error") or "-",
        ]
        for event in queries
        if int(event.get("result_count", 0) or 0) == 0
    ]
    print("Zero-result queries")
    if zero_results:
        print_table(["City", "Niche", "Source", "Error"], zero_results)
    else:
        print("None")
    print()

    slowest = sorted(
        queries,
        key=lambda event: float(event.get("duration_s", 0) or 0),
        reverse=True,
    )[:10]
    print("Top 10 slowest queries")
    print_table(
        ["City", "Niche", "Source", "Results", "Duration (s)"],
        [
            [
                event.get("city", ""),
                event.get("niche", ""),
                event.get("source", ""),
                int(event.get("result_count", 0) or 0),
                f"{float(event.get('duration_s', 0) or 0):.3f}",
            ]
            for event in slowest
        ],
    )
    print()


def print_stage_coverage(events: list[dict]) -> None:
    leads = [event for event in events if event.get("event") == "lead"]

    print("## Stage Coverage")
    if not leads:
        print("No lead events found.")
        print()
        return

    total = len(leads)
    status_counts = Counter(event.get("website_status", "UNKNOWN") for event in leads)
    print("Website status breakdown")
    print_table(
        ["Status", "Count", "Percent"],
        [
            [status, count, f"{(count / total) * 100:.1f}%"]
            for status, count in sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    )
    print()

    stage_checks = [
        ("emails_found > 0", lambda stages: int(stages.get("emails_found", 0) or 0) > 0),
        ("json_ld_found", lambda stages: bool(stages.get("json_ld_found"))),
        ("instagram_handle_found", lambda stages: bool(stages.get("instagram_handle_found"))),
        ("contact_discovery_run", lambda stages: bool(stages.get("contact_discovery_run"))),
    ]
    print("Per-stage coverage")
    print_table(
        ["Stage", "Count", "Percent"],
        [
            [
                label,
                count,
                f"{(count / total) * 100:.1f}%",
            ]
            for label, count in (
                (
                    label,
                    sum(1 for event in leads if check(event.get("stages", {}))),
                )
                for label, check in stage_checks
            )
        ],
    )
    print()


def print_score_distribution(events: list[dict]) -> None:
    leads = [event for event in events if event.get("event") == "lead"]

    print("## Score Distribution")
    if not leads:
        print("No lead events found.")
        print()
        return

    tier_counts = Counter(int(event.get("tier", 0) or 0) for event in leads)
    print("Tier distribution")
    print_table(
        ["Tier", "Count"],
        [[tier, tier_counts.get(tier, 0)] for tier in sorted(tier_counts)],
    )
    print()

    city_scores: dict[str, list[float]] = defaultdict(list)
    for event in leads:
        city = event.get("city")
        score = event.get("score")
        if city is None or score is None:
            continue
        city_scores[str(city)].append(float(score))

    print("Average score by city")
    print_table(
        ["City", "Count", "Average Score"],
        [
            [city, len(scores), f"{sum(scores) / len(scores):.2f}"]
            for city, scores in sorted(
                city_scores.items(),
                key=lambda item: (sum(item[1]) / len(item[1]), item[0]),
                reverse=True,
            )
        ],
    )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze structured pipeline JSONL logs.")
    parser.add_argument("log_path", nargs="?", help="Path to a pipeline_*.jsonl file")
    args = parser.parse_args()

    try:
        log_path = resolve_log_path(args.log_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    events = load_events(log_path)
    print(f"Analyzing: {log_path}")
    print()
    print_run_summary(events)
    print_query_coverage(events)
    print_stage_coverage(events)
    print_score_distribution(events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
