"""
Entry point for running the lead discovery pipeline.

Usage
-----
    python -m src.main --config config/markets.json --output data/leads.json
    python -m src.main --config config/markets.json --output data/leads.csv --format csv
    python -m src.main --config config/markets.json --output -   # stdout JSON
"""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time

from .logging_utils import generate_run_id
from .pipeline import LeadPipeline
from .output.exporter_json import export_json
from .output.exporter_csv import export_csv
from .search_vocabulary import build_search_variants, get_search_languages
from .terminal_logging import TerminalRunLogger


_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def main():
    parser = argparse.ArgumentParser(description="Run SMB lead discovery pipeline")
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "config" / "markets.json"),
        help="Path to the JSON configuration file",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("GOOGLE_PLACES_API_KEY"),
        help="Google Places API key (or set GOOGLE_PLACES_API_KEY env var)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output file path, or '-' for stdout (default: stdout)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv"],
        default=None,
        help="Output format: json or csv (default: inferred from --output extension, else json)",
    )
    parser.add_argument(
        "--terminal-verbosity",
        type=str,
        choices=["normal", "verbose", "debug"],
        default=None,
        help="Terminal transcript verbosity (default: config value or normal)",
    )
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit(
            "A Google Places API key is required. "
            "Provide via --api-key or GOOGLE_PLACES_API_KEY environment variable."
        )

    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Determine output format
    fmt = args.format
    if fmt is None:
        if args.output and args.output != "-" and args.output.endswith(".csv"):
            fmt = "csv"
        else:
            fmt = config.get("output_format", "json")

    output_path = None if args.output == "-" else args.output
    run_id = generate_run_id()
    terminal_verbosity = args.terminal_verbosity or config.get("terminal_verbosity", "normal")
    terminal_summary_every_queries = config.get("terminal_summary_every_queries", 5)
    search_languages = get_search_languages(config)
    total_queries = (
        len(config.get("countries", []))
        * len(config.get("cities", []))
        * sum(
            len(build_search_variants(niche, search_languages))
            for niche in config.get("niches", [])
        )
    )

    with TerminalRunLogger(
        run_id,
        _LOG_DIR,
        verbosity=terminal_verbosity,
        summary_every_queries=terminal_summary_every_queries,
    ) as terminal:
        terminal.run_start(
            entry_point="src.main",
            config=config,
            total_queries=total_queries,
            structured_log_path=_LOG_DIR / f"pipeline_{run_id}.jsonl",
        )

        start = time.monotonic()
        pipeline = LeadPipeline(
            config=config,
            api_key=args.api_key,
            run_id=run_id,
            terminal_logger=terminal,
        )
        leads = pipeline.run()
        elapsed = time.monotonic() - start
        leads_data = [lead.to_json() for lead in leads]
        website_status_counts = Counter(lead.website_status.value for lead in leads)

        terminal.batch(name="pipeline", detail=f"done leads={len(leads)} duration={elapsed:.1f}s")
        terminal.final_summary(
            total_leads=len(leads),
            duration_s=elapsed,
            website_status_counts=website_status_counts,
        )

        terminal.batch(name="export", detail=f"start format={fmt} lead_count={len(leads_data)}")
        if fmt == "csv":
            export_csv(leads_data, output_path)
            terminal.export_complete(artifact="csv", path=output_path or "stdout")
        else:
            export_json(leads_data, output_path)
            terminal.export_complete(artifact="json", path=output_path or "stdout")

        if output_path:
            print(f"Wrote {len(leads_data)} leads to {output_path}")
        else:
            import sys
            print(f"\n# {len(leads_data)} leads exported.", file=sys.stderr)


if __name__ == "__main__":
    main()
