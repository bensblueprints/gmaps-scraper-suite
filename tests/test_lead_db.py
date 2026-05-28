"""Tests for shared/lead_db.py — uses a temp in-memory/temp-file DB."""
import sys
import csv
import sqlite3
import tempfile
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import shared.lead_db as lead_db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a fresh temp file per test."""
    db_path = tmp_path / "test_leads.db"
    monkeypatch.setattr(lead_db, "DB_PATH", db_path)
    lead_db.init()
    yield db_path


def _sample_lead(**overrides):
    base = {
        "title":        "Acme Plumbing",
        "phone":        "+1-702-555-0100",
        "email":        "info@acmeplumbing.com",
        "platform":     "WordPress",
        "address":      "123 Main St, Las Vegas, NV 89101, USA",
        "website":      "https://acmeplumbing.com",
        "category":     "Plumber",
        "review_rating": "4.8",
        "review_count": "312",
        "latitude":     "36.1699",
        "longitude":    "-115.1398",
        "contact_url":  "https://acmeplumbing.com/contact",
        "industry":     "Plumbers",
        "scraped_at":   "2026-05-28T10:00:00",
    }
    base.update(overrides)
    return base


class TestUpsert:
    def test_insert_returns_true(self):
        lead = _sample_lead()
        assert lead_db.upsert(lead) is True

    def test_duplicate_returns_false(self):
        lead = _sample_lead()
        lead_db.upsert(lead)
        assert lead_db.upsert(lead) is False

    def test_different_phone_is_new(self):
        lead_db.upsert(_sample_lead(phone="555-0001"))
        assert lead_db.upsert(_sample_lead(phone="555-0002")) is True

    def test_emails_list_takes_first(self):
        lead = _sample_lead(emails=["first@biz.com", "second@biz.com"], email="")
        lead_db.upsert(lead)
        rows = lead_db.get_all()
        assert rows[0]["email"] == "first@biz.com"

    def test_email_field_used_when_no_emails_list(self):
        lead = _sample_lead(email="direct@biz.com")
        lead_db.upsert(lead)
        rows = lead_db.get_all()
        assert rows[0]["email"] == "direct@biz.com"

    def test_city_state_parsed_from_address(self):
        lead = _sample_lead(address="456 Oak Ave, Henderson, NV 89002, USA")
        lead_db.upsert(lead)
        row = lead_db.get_all()[0]
        assert row["city"] == "Henderson"
        assert row["state"] == "NV"

    def test_missing_address_gives_empty_city_state(self):
        lead = _sample_lead(address="")
        lead_db.upsert(lead)
        row = lead_db.get_all()[0]
        assert row["city"] == ""
        assert row["state"] == ""

    def test_name_from_title_field(self):
        lead = _sample_lead(title="Best Plumbers Inc")
        lead_db.upsert(lead)
        row = lead_db.get_all()[0]
        assert row["name"] == "Best Plumbers Inc"

    def test_name_from_name_field(self):
        lead = {"name": "Name-only Lead", "phone": "555-9999"}
        lead_db.upsert(lead)
        row = lead_db.get_all()[0]
        assert row["name"] == "Name-only Lead"


class TestCount:
    def test_empty_db_is_zero(self):
        assert lead_db.count() == 0

    def test_count_increments(self):
        lead_db.upsert(_sample_lead(phone="001"))
        lead_db.upsert(_sample_lead(phone="002"))
        assert lead_db.count() == 2

    def test_duplicate_doesnt_increment(self):
        lead = _sample_lead()
        lead_db.upsert(lead)
        lead_db.upsert(lead)
        assert lead_db.count() == 1


class TestGetAll:
    def test_returns_list_of_dicts(self):
        lead_db.upsert(_sample_lead())
        rows = lead_db.get_all()
        assert isinstance(rows, list)
        assert isinstance(rows[0], dict)

    def test_search_by_name(self):
        lead_db.upsert(_sample_lead(title="Acme Plumbing", phone="001",
                                    email="info@acmeplumbing.com"))
        lead_db.upsert(_sample_lead(title="Best Electric", phone="002",
                                    email="info@bestelectric.com"))
        results = lead_db.get_all(search="Acme")
        assert len(results) == 1
        assert results[0]["name"] == "Acme Plumbing"

    def test_search_by_phone(self):
        lead_db.upsert(_sample_lead(phone="702-555-1234"))
        lead_db.upsert(_sample_lead(phone="702-555-9999"))
        results = lead_db.get_all(search="1234")
        assert len(results) == 1

    def test_search_by_email(self):
        lead_db.upsert(_sample_lead(email="owner@targetco.com", phone="001"))
        lead_db.upsert(_sample_lead(email="other@other.com", phone="002"))
        results = lead_db.get_all(search="targetco")
        assert len(results) == 1

    def test_empty_search_returns_all(self):
        lead_db.upsert(_sample_lead(phone="001"))
        lead_db.upsert(_sample_lead(phone="002"))
        assert len(lead_db.get_all()) == 2

    def test_limit_respected(self):
        for i in range(10):
            lead_db.upsert(_sample_lead(phone=f"55500{i:02d}"))
        assert len(lead_db.get_all(limit=3)) == 3

    def test_ordered_newest_first(self):
        lead_db.upsert(_sample_lead(phone="001"))
        lead_db.upsert(_sample_lead(phone="002"))
        rows = lead_db.get_all()
        assert rows[0]["phone"] == "002"


class TestExportCsv:
    def test_exports_rows(self, tmp_path):
        lead_db.upsert(_sample_lead(phone="001"))
        lead_db.upsert(_sample_lead(phone="002"))
        out = str(tmp_path / "export.csv")
        count = lead_db.export_csv(out)
        assert count == 2
        with open(out, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_export_empty_returns_zero(self, tmp_path):
        out = str(tmp_path / "empty.csv")
        assert lead_db.export_csv(out) == 0

    def test_csv_has_expected_headers(self, tmp_path):
        lead_db.upsert(_sample_lead())
        out = str(tmp_path / "headers.csv")
        lead_db.export_csv(out)
        with open(out, newline='', encoding='utf-8') as f:
            headers = next(csv.reader(f))
        for field in ('name', 'phone', 'email', 'platform', 'city', 'state'):
            assert field in headers


class TestCityStateParsing:
    def test_standard_us_address(self):
        city, state = lead_db._city_state("123 Main St, Las Vegas, NV 89101, USA")
        assert city == "Las Vegas"
        assert state == "NV"

    def test_two_part_address(self):
        city, state = lead_db._city_state("Henderson, NV")
        assert city == ""  # less than 3 parts

    def test_empty_address(self):
        city, state = lead_db._city_state("")
        assert city == ""
        assert state == ""

    def test_none_address(self):
        city, state = lead_db._city_state(None)
        assert city == ""
        assert state == ""


class TestThreadSafety:
    def test_concurrent_inserts_no_crash(self):
        errors = []
        def insert(n):
            try:
                lead_db.upsert(_sample_lead(phone=f"THREAD-{n}", title=f"Biz {n}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=insert, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert lead_db.count() == 20
