from __future__ import annotations

import json
import re
from pathlib import Path

from src.enums import WebsiteStatus
from src.logging_utils import PipelineLogger, generate_run_id
from src.models import BusinessLead


def _read_events(log_dir: Path, run_id: str) -> list[dict]:
    log_path = log_dir / f"pipeline_{run_id}.jsonl"
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _build_lead() -> BusinessLead:
    lead = BusinessLead(
        company_name="Smile Dental",
        niche="dentist",
        country="DE",
        city="Berlin",
        website_url="https://example.com",
    )
    lead.website_status = WebsiteStatus.HAS_WEBSITE
    lead.lead_priority_score = 72.25
    lead.tier = 2
    lead.all_emails = ["hello@example.com"]
    return lead


def test_log_run_start_writes_expected_json(tmp_path):
    run_id = "20260318_120000"
    logger = PipelineLogger(run_id, tmp_path)

    logger.log_run_start({
        "cities": ["Berlin", "Munich"],
        "niches": ["dentist"],
        "countries": ["DE"],
        "search_languages": ["en", "de"],
        "max_results_per_query": 5,
    })
    logger.close()

    [event] = _read_events(tmp_path, run_id)
    assert event["event"] == "run_start"
    assert event["run_id"] == run_id
    assert event["config_cities"] == ["Berlin", "Munich"]
    assert event["config_niches"] == ["dentist"]
    assert event["config_countries"] == ["DE"]
    assert event["config_search_languages"] == ["en", "de"]
    assert event["max_results_per_query"] == 5
    assert isinstance(event["ts"], str)


def test_log_query_writes_expected_event(tmp_path):
    run_id = "20260318_120001"
    logger = PipelineLogger(run_id, tmp_path)

    logger.log_query(
        "Berlin",
        "dentist",
        "google_places",
        7,
        1.234,
        search_language="uk",
        fallback=False,
        error=None,
    )
    logger.close()

    [event] = _read_events(tmp_path, run_id)
    assert event == {
        "event": "query",
        "run_id": run_id,
        "ts": event["ts"],
        "city": "Berlin",
        "niche": "dentist",
        "search_language": "uk",
        "source": "google_places",
        "result_count": 7,
        "duration_s": 1.234,
        "fallback": False,
        "error": None,
    }


def test_log_lead_writes_nested_stages(tmp_path):
    run_id = "20260318_120002"
    logger = PipelineLogger(run_id, tmp_path)
    lead = _build_lead()
    stages = {
        "website_fetched": True,
        "audit_run": True,
        "json_ld_found": False,
        "emails_found": 1,
        "social_links_found": 2,
        "instagram_handle_found": False,
        "contact_discovery_run": True,
    }

    logger.log_lead(lead, stages, 2.75)
    logger.close()

    [event] = _read_events(tmp_path, run_id)
    assert event["event"] == "lead"
    assert event["company"] == "Smile Dental"
    assert event["city"] == "Berlin"
    assert event["niche"] == "dentist"
    assert event["website_status"] == "HAS_WEBSITE"
    assert event["score"] == 72.25
    assert event["tier"] == 2
    assert event["duration_s"] == 2.75
    assert event["stages"] == stages


def test_close_and_context_manager_close_file_handle(tmp_path):
    run_id = "20260318_120003"
    logger = PipelineLogger(run_id, tmp_path)
    logger.log_run_end(3, 4.5)
    logger.close()
    assert logger._fh.closed

    with PipelineLogger("20260318_120004", tmp_path) as managed_logger:
        managed_logger.log_run_end(1, 1.0)

    assert managed_logger._fh.closed


def test_generate_run_id_matches_expected_format():
    assert re.fullmatch(r"\d{8}_\d{6}", generate_run_id())
