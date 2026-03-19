from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.enums import InstagramStatus, WebsiteStatus
from src.terminal_logging import TerminalRunLogger


def test_terminal_run_logger_creates_transcript_and_captures_terminal_streams(tmp_path, capsys):
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    with TerminalRunLogger("20260318_130000", tmp_path) as terminal:
        terminal.batch(name="pipeline", detail="start")
        logging.getLogger(__name__).info("module-log-message")
        print("stdout-message")

    assert sys.stdout is original_stdout
    assert sys.stderr is original_stderr

    transcript = (tmp_path / "terminal_20260318_130000.log").read_text(encoding="utf-8")
    captured = capsys.readouterr()

    assert "[BATCH] pipeline start" in transcript
    assert "module-log-message" in transcript
    assert "stdout-message" in transcript
    assert "[BATCH] pipeline start" in captured.err
    assert "stdout-message" in captured.out


def test_terminal_run_logger_normal_mode_suppresses_routine_lead_lines_and_emits_summaries(tmp_path):
    structured_log = tmp_path / "pipeline_20260318_130001.jsonl"

    with TerminalRunLogger(
        "20260318_130001",
        tmp_path,
        verbosity="normal",
        summary_every_queries=1,
    ) as terminal:
        terminal.run_start(
            entry_point="test.entry",
            config={"cities": ["Berlin"], "niches": ["dentist"]},
            total_queries=1,
            structured_log_path=structured_log,
        )
        terminal.query_start(index=1, total=1, city="Berlin", niche="dentist")
        terminal.query_result(
            city="Berlin",
            niche="dentist",
            source="overpass",
            result_count=0,
            duration_s=12.5,
            status="zero_results",
            retry_count=2,
            error="overpass_timeout",
        )
        terminal.lead_stage(company="Acme Dental", stage="start", detail="city=Berlin niche=dentist")
        terminal.lead_complete(
            company="Acme Dental",
            city="Berlin",
            niche="dentist",
            website_status="BROKEN_WEBSITE",
            tier=2,
            score=58.4,
        )
        terminal.city_complete(
            city="Berlin",
            completed_queries=1,
            total_queries=1,
            leads_before_dedup=1,
        )
        terminal.dedup_complete(before=3, after=2, sample_reasons=["root_domain=example.com"])
        terminal.final_summary(
            total_leads=2,
            duration_s=12.5,
            website_status_counts={"BROKEN_WEBSITE": 1, "NO_WEBSITE": 1},
        )

    transcript = (tmp_path / "terminal_20260318_130001.log").read_text(encoding="utf-8")

    assert "verbosity=normal" in transcript
    assert "status=zero_results" in transcript
    assert "retries=2" in transcript
    assert "[ANOMALY] query" in transcript
    assert "[ANOMALY] lead company=Acme Dental" in transcript
    assert "[LEAD] company=Acme Dental stage=start" not in transcript
    assert "[SUMMARY] city city=Berlin" in transcript
    assert "sample=root_domain=example.com" in transcript
    assert "[SUMMARY] run total_leads=2 duration=12.5s warnings=0 zero_results=1 retries=2" in transcript
    assert "[SUMMARY] website_statuses BROKEN_WEBSITE=1 NO_WEBSITE=1" in transcript


def test_terminal_run_logger_verbose_mode_emits_lead_stage_lines(tmp_path):
    with TerminalRunLogger("20260318_130002", tmp_path, verbosity="verbose") as terminal:
        terminal.lead_stage(company="Verbose Co", stage="website", detail="status=NO_WEBSITE")
        terminal.lead_complete(
            company="Verbose Co",
            city="Lisbon",
            niche="restaurant",
            website_status="NO_WEBSITE",
            tier=3,
            score=47.0,
        )

    transcript = (tmp_path / "terminal_20260318_130002.log").read_text(encoding="utf-8")
    assert "[LEAD] company=Verbose Co stage=website status=NO_WEBSITE" in transcript
    assert "[LEAD] complete company=Verbose Co city=Lisbon niche=restaurant website=NO_WEBSITE tier=3 score=47.0" in transcript


def test_src_main_creates_transcript_and_step_logs(tmp_path, monkeypatch):
    config_path = tmp_path / "main_config.json"
    output_path = tmp_path / "leads.json"
    config_path.write_text(json.dumps({
        "countries": ["DE"],
        "cities": ["Berlin"],
        "niches": ["dentist"],
        "language_priority": ["en"],
        "max_results_per_query": 5,
        "min_reviews_threshold": 0,
        "min_rating_threshold": 0.0,
        "include_instagram_analysis": False,
        "run_website_audit": False,
        "request_delay": 0,
        "terminal_summary_every_queries": 1,
        "output_format": "json",
    }), encoding="utf-8")

    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", [
        "python",
        "--config",
        str(config_path),
        "--output",
        str(output_path),
        "--format",
        "json",
    ])

    with patch("src.pipeline.GooglePlacesCollector") as MockGPC, \
         patch("src.pipeline.WebsiteCollector") as MockWC, \
         patch("src.pipeline.InstagramSignalCollector") as MockIG:
        mock_places = MagicMock()
        mock_places.search.return_value = [{
            "id": "place_main_001",
            "displayName": {"text": "Smile Dental Berlin"},
            "formattedAddress": "Unter den Linden 1, Berlin",
            "rating": 4.6,
            "userRatingCount": 88,
        }]
        mock_places.get_place_details.return_value = {
            "id": "place_main_001",
            "internationalPhoneNumber": "+49 30 12345678",
            "websiteUri": None,
            "googleMapsUri": "https://maps.google.com/?cid=12345",
            "rating": 4.6,
            "userRatingCount": 88,
        }
        MockGPC.return_value = mock_places

        mock_website = MagicMock()
        mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
        MockWC.return_value = mock_website

        mock_ig = MagicMock()
        mock_ig.extract_handle_from_html.return_value = None
        mock_ig.analyze_handle.return_value = InstagramStatus.UNKNOWN
        MockIG.return_value = mock_ig

        import src.main as main_module
        import src.pipeline as pipeline_module

        log_dir = tmp_path / "logs"
        monkeypatch.setattr(main_module, "_LOG_DIR", log_dir)
        monkeypatch.setattr(pipeline_module, "_LOG_DIR", log_dir)

        main_module.main()

    transcript = next(log_dir.glob("terminal_*.log"))
    structured_log = next(log_dir.glob("pipeline_*.jsonl"))
    transcript_text = transcript.read_text(encoding="utf-8")

    assert output_path.exists()
    assert structured_log.exists()
    assert "[RUN] entry=src.main" in transcript_text
    assert "verbosity=normal" in transcript_text
    assert "[QUERY 1/1] start city=Berlin niche=dentist" in transcript_text
    assert "[QUERY] done city=Berlin niche=dentist source=google_places results=1 duration=" in transcript_text
    assert "status=success" in transcript_text
    assert "retries=0" in transcript_text
    assert "[SUMMARY] city city=Berlin" in transcript_text
    assert "[SUMMARY] run total_leads=1" in transcript_text
    assert "[BATCH] dedup done before=1 after=1 removed=0" in transcript_text
    assert "[EXPORT] json path=" in transcript_text
    assert "[LEAD] company=Smile Dental Berlin stage=start" not in transcript_text


def test_run_europe_smb_creates_transcript_and_step_logs(tmp_path, monkeypatch):
    output_json = tmp_path / "osm_leads.json"
    output_csv = tmp_path / "osm_leads.csv"
    output_summary = tmp_path / "osm_summary.md"
    config_path = tmp_path / "osm_config.json"
    config_path.write_text(json.dumps({
        "countries": ["Portugal"],
        "cities": ["Lisbon"],
        "city_country_map": {"Lisbon": "Portugal"},
        "niches": ["restaurant"],
        "max_results_per_query": 5,
        "min_reviews_threshold": 0,
        "min_rating_threshold": 0.0,
        "include_instagram_analysis": False,
        "run_website_audit": False,
        "request_delay": 0,
        "enable_social_discovery": False,
        "enable_contact_discovery": False,
        "enable_tripadvisor_discovery": False,
        "enable_email_guesser": False,
        "terminal_summary_every_queries": 1,
        "output": {
            "json": str(output_json),
            "csv": str(output_csv),
            "summary": str(output_summary),
        },
    }), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["python", "--config", str(config_path)])

    with patch("run_europe_smb.OverpassCollector") as MockOPC, \
         patch("run_europe_smb.WebsiteCollector") as MockWC, \
         patch("run_europe_smb.InstagramSignalCollector") as MockIG:
        mock_collector = MagicMock()
        mock_collector.search.return_value = [{
            "id": "osm_runner_001",
            "displayName": {"text": "Lisbon Bistro"},
            "formattedAddress": "Rua Augusta, Lisbon",
            "rating": None,
            "userRatingCount": None,
        }]
        mock_collector.get_place_details.return_value = {
            "id": "osm_runner_001",
            "internationalPhoneNumber": "+351 21 123 4567",
            "websiteUri": None,
            "googleMapsUri": "https://maps.google.com/?cid=67890",
            "formattedAddress": "Rua Augusta, Lisbon",
            "_niche": "restaurant",
            "_osm_tags": {},
        }
        mock_collector.last_query_meta = {
            "status": "success",
            "retry_count": 0,
            "error": None,
        }
        MockOPC.return_value = mock_collector

        mock_website = MagicMock()
        mock_website.check_website.return_value = (WebsiteStatus.NO_WEBSITE, None)
        MockWC.return_value = mock_website

        mock_ig = MagicMock()
        mock_ig.extract_handle_from_html.return_value = None
        mock_ig.analyze_handle.return_value = InstagramStatus.UNKNOWN
        MockIG.return_value = mock_ig

        import run_europe_smb as runner_module

        log_dir = tmp_path / "logs"
        monkeypatch.setattr(runner_module, "LOG_DIR", log_dir)
        runner_module.main()

    transcript = next(log_dir.glob("terminal_*.log"))
    structured_log = next(log_dir.glob("pipeline_*.jsonl"))
    transcript_text = transcript.read_text(encoding="utf-8")

    assert output_json.exists()
    assert output_csv.exists()
    assert output_summary.exists()
    assert structured_log.exists()
    assert "[RUN] entry=run_europe_smb.py" in transcript_text
    assert "verbosity=normal" in transcript_text
    assert "[QUERY 1/1] start city=Lisbon niche=restaurant" in transcript_text
    assert "[QUERY] done city=Lisbon niche=restaurant source=overpass results=1 duration=" in transcript_text
    assert "status=success" in transcript_text
    assert "retries=0" in transcript_text
    assert "[SUMMARY] city city=Lisbon" in transcript_text
    assert "[SUMMARY] run total_leads=1" in transcript_text
    assert "[BATCH] dedup done before=1 after=1 removed=0" in transcript_text
    assert "[EXPORT] summary path=" in transcript_text
    assert "[LEAD] company=Lisbon Bistro stage=start" not in transcript_text
