"""Tests for scraper_node/engine.py"""
import sys
import csv
import threading
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scraper_node"))

import pytest
from unittest.mock import patch, MagicMock
import shared.lead_db as lead_db
from engine import ScraperEngine


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(lead_db, "DB_PATH", tmp_path / "test.db")
    lead_db.init()


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    from shared import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    eng = ScraperEngine(log_callback=lambda msg: None)
    return eng


def _make_lead(name="Acme", phone="555-0001", website="https://acme.com", **kw):
    return {
        "title": name, "phone": phone, "website": website,
        "address": "1 Main St, Las Vegas, NV 89101",
        "category": "Plumber", "review_rating": "4.5", "review_count": "50",
        "latitude": "36.1", "longitude": "-115.1",
        **kw
    }


class TestEnrichBatch:
    def test_returns_all_leads(self, engine):
        leads = [_make_lead(name=f"Biz{i}", phone=f"55500{i}") for i in range(3)]
        fake_info = {"platform": "WordPress", "emails": ["a@biz.com"], "contact_url": ""}

        with patch("shared.website_enricher.enrich", return_value=fake_info):
            results = engine._enrich_batch(leads, extract_email=True, on_lead=None)

        assert len(results) == 3

    def test_platform_and_email_populated(self, engine):
        leads = [_make_lead()]
        fake_info = {"platform": "Shopify", "emails": ["shop@biz.com"], "contact_url": ""}

        with patch("shared.website_enricher.enrich", return_value=fake_info):
            results = engine._enrich_batch(leads, extract_email=True, on_lead=None)

        assert results[0]["platform"] == "Shopify"
        assert results[0]["email"] == "shop@biz.com"
        assert results[0]["emails"] == ["shop@biz.com"]

    def test_skip_enrichment_when_no_website(self, engine):
        leads = [_make_lead(website="")]
        with patch("shared.website_enricher.enrich") as mock_enrich:
            engine._enrich_batch(leads, extract_email=True, on_lead=None)
        mock_enrich.assert_not_called()

    def test_skip_enrichment_when_extract_email_false(self, engine):
        leads = [_make_lead()]
        with patch("shared.website_enricher.enrich") as mock_enrich:
            engine._enrich_batch(leads, extract_email=False, on_lead=None)
        mock_enrich.assert_not_called()

    def test_on_lead_callback_called(self, engine):
        leads = [_make_lead(name=f"Biz{i}", phone=f"55500{i}") for i in range(3)]
        fake_info = {"platform": "", "emails": [], "contact_url": ""}
        received = []

        with patch("shared.website_enricher.enrich", return_value=fake_info):
            engine._enrich_batch(leads, extract_email=True, on_lead=lambda l: received.append(l))

        assert len(received) == 3

    def test_stop_event_short_circuits(self, engine):
        leads = [_make_lead(name=f"Biz{i}", phone=f"55500{i}") for i in range(10)]
        engine._stop_event.set()
        with patch("shared.website_enricher.enrich") as mock_enrich:
            engine._enrich_batch(leads, extract_email=True, on_lead=None)
        mock_enrich.assert_not_called()

    def test_enrich_exception_doesnt_crash_batch(self, engine):
        leads = [_make_lead(name=f"Biz{i}", phone=f"55500{i}") for i in range(3)]
        with patch("shared.website_enricher.enrich", side_effect=Exception("timeout")):
            results = engine._enrich_batch(leads, extract_email=True, on_lead=None)
        assert len(results) == 3

    def test_leads_upserted_to_db(self, engine):
        leads = [_make_lead(name=f"Biz{i}", phone=f"55500{i}") for i in range(3)]
        fake_info = {"platform": "Wix", "emails": [], "contact_url": ""}
        with patch("shared.website_enricher.enrich", return_value=fake_info):
            engine._enrich_batch(leads, extract_email=True, on_lead=None)
        assert lead_db.count() == 3


class TestSaveToCsv:
    def test_creates_file(self, engine, tmp_path, monkeypatch):
        import engine as eng_module
        monkeypatch.setattr(eng_module, "OUTPUT_DIR", tmp_path)
        rows = [_make_lead(name="Acme", phone="001")]
        count = engine._save_to_csv(rows, "Plumbers")
        assert count == 1
        files = list(tmp_path.glob("plumbers.csv"))
        assert files

    def test_returns_row_count(self, engine, tmp_path, monkeypatch):
        import engine as eng_module
        monkeypatch.setattr(eng_module, "OUTPUT_DIR", tmp_path)
        rows = [_make_lead(name=f"B{i}", phone=f"00{i}") for i in range(5)]
        assert engine._save_to_csv(rows, "Test Industry") == 5

    def test_appends_on_second_call(self, engine, tmp_path, monkeypatch):
        import engine as eng_module
        monkeypatch.setattr(eng_module, "OUTPUT_DIR", tmp_path)
        engine._save_to_csv([_make_lead(phone="001")], "Plumbers")
        engine._save_to_csv([_make_lead(phone="002")], "Plumbers")
        out = tmp_path / "plumbers.csv"
        with open(out, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_empty_rows_returns_zero(self, engine, tmp_path, monkeypatch):
        import engine as eng_module
        monkeypatch.setattr(eng_module, "OUTPUT_DIR", tmp_path)
        assert engine._save_to_csv([], "Plumbers") == 0

    def test_slugifies_industry_name(self, engine, tmp_path, monkeypatch):
        import engine as eng_module
        monkeypatch.setattr(eng_module, "OUTPUT_DIR", tmp_path)
        engine._save_to_csv([_make_lead()], "HVAC & Heating")
        assert (tmp_path / "hvac_and_heating.csv").exists()

    def test_priority_columns_come_first(self, engine, tmp_path, monkeypatch):
        import engine as eng_module
        monkeypatch.setattr(eng_module, "OUTPUT_DIR", tmp_path)
        engine._save_to_csv([_make_lead()], "Test")
        out = tmp_path / "test.csv"
        with open(out, newline='', encoding='utf-8') as f:
            headers = next(csv.reader(f))
        assert headers[0] == "title"
        assert headers[1] == "phone"


class TestDeduplication:
    """Deduplication runs inside run_industry — test the logic separately."""

    def test_same_phone_name_deduped(self):
        results = [
            {"title": "Acme", "phone": "555-001"},
            {"title": "Acme", "phone": "555-001"},
            {"title": "Acme", "phone": "555-001"},
        ]
        seen = set()
        unique = []
        for r in results:
            key = (r.get("phone", ""), r.get("title", "").lower())
            if key not in seen:
                seen.add(key)
                unique.append(r)
        assert len(unique) == 1

    def test_different_phones_kept(self):
        results = [
            {"title": "Acme", "phone": "555-001"},
            {"title": "Acme", "phone": "555-002"},
        ]
        seen = set()
        unique = []
        for r in results:
            key = (r.get("phone", ""), r.get("title", "").lower())
            if key not in seen:
                seen.add(key)
                unique.append(r)
        assert len(unique) == 2
