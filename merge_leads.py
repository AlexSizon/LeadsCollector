#!/usr/bin/env python3
"""
merge_leads.py — Merge supplemental lead files into the main output.

Usage
-----
    python merge_leads.py                    # default: merge all output/leads_*.json supplements
    python merge_leads.py output/leads_portugal_supplement.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.enrichment.deduplicator import deduplicate_leads
from src.models import BusinessLead
from src.output.exporter_json import export_json
from src.output.exporter_csv import export_csv


MAIN_JSON = ROOT / "output" / "leads.json"
MAIN_CSV  = ROOT / "output" / "leads.csv"
MAIN_SUMMARY = ROOT / "output" / "run_summary.md"


def load_leads_from_file(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("leads", [])


def main():
    supplement_files: list[Path]
    if len(sys.argv) > 1:
        supplement_files = [Path(a) for a in sys.argv[1:]]
    else:
        supplement_files = sorted(ROOT.glob("output/leads_*supplement*.json"))

    if not supplement_files:
        print("No supplement files found. Pass paths as arguments or drop files into output/.")
        sys.exit(0)

    print(f"Loading main database: {MAIN_JSON}")
    existing = load_leads_from_file(MAIN_JSON)
    print(f"  {len(existing)} leads loaded")

    total_new = 0
    for sup in supplement_files:
        sup_leads = load_leads_from_file(sup)
        print(f"  + {len(sup_leads)} leads from {sup.name}")
        existing.extend(sup_leads)
        total_new += len(sup_leads)

    print(f"Combined pool: {len(existing)} leads — deduplicating...")

    # Convert dicts → BusinessLead objects for dedup, then back to dicts
    # The deduplicator works on BusinessLead objects
    from src.enums import WebsiteStatus, InstagramStatus

    def dict_to_lead(d: dict) -> BusinessLead:
        d2 = dict(d)
        try:
            d2["website_status"] = WebsiteStatus(d2.get("website_status", "unknown"))
        except ValueError:
            d2["website_status"] = WebsiteStatus.UNKNOWN
        try:
            d2["instagram_status"] = InstagramStatus(d2.get("instagram_status", "unknown"))
        except ValueError:
            d2["instagram_status"] = InstagramStatus.UNKNOWN
        # Remove fields not in model
        known = {f.name for f in BusinessLead.__dataclass_fields__.values()} if hasattr(BusinessLead, "__dataclass_fields__") else set()
        if known:
            d2 = {k: v for k, v in d2.items() if k in known}
        return BusinessLead(**{k: v for k, v in d2.items()
                               if k in BusinessLead.__init__.__code__.co_varnames})

    # Use BusinessLead field names from model inspection
    import inspect
    lead_params = set(inspect.signature(BusinessLead.__init__).parameters.keys()) - {"self"}

    def safe_dict_to_lead(d: dict) -> BusinessLead:
        d2 = {k: v for k, v in d.items() if k in lead_params}
        try:
            d2["website_status"] = WebsiteStatus(d2.get("website_status", "unknown"))
        except ValueError:
            d2["website_status"] = WebsiteStatus.UNKNOWN
        try:
            d2["instagram_status"] = InstagramStatus(d2.get("instagram_status", "unknown"))
        except ValueError:
            d2["instagram_status"] = InstagramStatus.UNKNOWN
        return BusinessLead(**d2)

    lead_objs = [safe_dict_to_lead(d) for d in existing]
    deduped   = deduplicate_leads(lead_objs)
    deduped_dicts = [l.to_json() for l in deduped]

    print(f"After dedup: {len(deduped_dicts)} leads (removed {len(existing) - len(deduped_dicts)} duplicates)")

    export_json(deduped_dicts, str(MAIN_JSON))
    print(f"Saved → {MAIN_JSON}")

    export_csv(deduped_dicts, str(MAIN_CSV))
    print(f"Saved → {MAIN_CSV}")

    # Update summary stats
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    country_counts: dict[str, int] = {}
    niche_counts:   dict[str, int] = {}
    ws_counts:      dict[str, int] = {}
    for lead in deduped:
        t = getattr(lead, "tier", 4)
        tier_counts[t] = tier_counts.get(t, 0) + 1
        c = getattr(lead, "country", "")
        country_counts[c] = country_counts.get(c, 0) + 1
        n = getattr(lead, "niche", "")
        niche_counts[n] = niche_counts.get(n, 0) + 1
        ws = lead.website_status.value
        ws_counts[ws] = ws_counts.get(ws, 0) + 1

    top10 = sorted(deduped, key=lambda l: l.lead_priority_score, reverse=True)[:10]

    summary_lines = [
        "# Europe SMB Lead Discovery — Merged Run Summary",
        f"\n**Total leads**: {len(deduped_dicts)}  ",
        f"**Countries**: Spain, Netherlands, Portugal  ",
        f"**Data source**: OpenStreetMap Overpass API  ",
        "\n## Tier Distribution",
        "| Tier | Count |",
        "|------|-------|",
        f"| 1 | {tier_counts[1]} |",
        f"| 2 | {tier_counts[2]} |",
        f"| 3 | {tier_counts[3]} |",
        f"| 4 | {tier_counts[4]} |",
        "\n## Website Status",
    ]
    for ws, cnt in sorted(ws_counts.items(), key=lambda x: -x[1]):
        summary_lines.append(f"- **{ws}**: {cnt}")
    summary_lines.append("\n## Leads by Country")
    for c, cnt in sorted(country_counts.items()):
        summary_lines.append(f"- {c}: {cnt}")
    summary_lines.append("\n## Leads by Niche")
    for n, cnt in sorted(niche_counts.items(), key=lambda x: -x[1]):
        summary_lines.append(f"- {n}: {cnt}")
    summary_lines.append("\n## Top 10 Leads by Priority Score")
    summary_lines.append("| # | Company | Niche | City | Country | Score | Tier | Website |")
    summary_lines.append("|---|---------|-------|------|---------|-------|------|---------|")
    for i, lead in enumerate(top10, 1):
        summary_lines.append(
            f"| {i} | {lead.company_name} | {lead.niche} | {lead.city} | "
            f"{lead.country} | {lead.lead_priority_score:.1f} | {lead.tier} | "
            f"{lead.website_status.value} |"
        )

    MAIN_SUMMARY.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Saved → {MAIN_SUMMARY}")
    print(f"\nDone. Database: {len(deduped_dicts)} leads.")


if __name__ == "__main__":
    main()
