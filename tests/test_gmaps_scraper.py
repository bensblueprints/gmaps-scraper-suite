"""Tests for scraper_node/gmaps_scraper.py — non-browser logic only."""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scraper_node"))

import pytest
from unittest.mock import MagicMock, patch
from gmaps_scraper import (
    is_chromium_installed,
    _get_item,
)


class TestGetItem:
    def _make_page(self, aria_label: str, use_starts_with: bool = False):
        """Build a minimal mock page for _get_item."""
        page = MagicMock()
        el = MagicMock()
        el.get_attribute.return_value = aria_label

        if use_starts_with:
            # exact match returns element with no aria-label, partial match returns real one
            exact_el = MagicMock()
            exact_el.get_attribute.return_value = ""
            page.locator.return_value.first = exact_el
            # second call (startswith) returns actual element
            page.locator.side_effect = [
                MagicMock(first=exact_el),
                MagicMock(first=el),
            ]
        else:
            page.locator.return_value.first = el

        return page

    def test_strips_address_prefix(self):
        page = self._make_page("Address: 123 Main St, Las Vegas, NV")
        result = _get_item(page, "address")
        assert result == "123 Main St, Las Vegas, NV"

    def test_strips_phone_prefix(self):
        page = self._make_page("Phone: +1 702-555-0100")
        result = _get_item(page, "phone")
        assert result == "+1 702-555-0100"

    def test_strips_website_prefix(self):
        page = self._make_page("Website: acmeplumbing.com")
        result = _get_item(page, "authority")
        assert result == "acmeplumbing.com"

    def test_returns_empty_on_exception(self):
        page = MagicMock()
        page.locator.side_effect = Exception("Timeout")
        result = _get_item(page, "address")
        assert result == ""

    def test_no_prefix_returns_label_as_is(self):
        page = self._make_page("Some random label")
        result = _get_item(page, "custom")
        assert result == "Some random label"


class TestRatingRegex:
    """Test the rating extraction regex patterns used in gmaps_scraper._extract_place."""

    STARS_RE = re.compile(r'aria-label="([\d.]+)\s+stars?\s*"')
    REVIEWS_RE = re.compile(r'aria-label="([\d,]+)\s+reviews?"')

    def test_stars_exact(self):
        html = 'aria-label="4.9 stars "'
        m = self.STARS_RE.search(html)
        assert m and m.group(1) == "4.9"

    def test_stars_no_trailing_space(self):
        html = 'aria-label="4.5 stars"'
        m = self.STARS_RE.search(html)
        assert m and m.group(1) == "4.5"

    def test_stars_singular(self):
        html = 'aria-label="1.0 star"'
        m = self.STARS_RE.search(html)
        assert m and m.group(1) == "1.0"

    def test_reviews_basic(self):
        html = 'aria-label="456 reviews"'
        m = self.REVIEWS_RE.search(html)
        assert m and m.group(1).replace(",", "") == "456"

    def test_reviews_singular(self):
        html = 'aria-label="1 review"'
        m = self.REVIEWS_RE.search(html)
        assert m and m.group(1) == "1"

    def test_reviews_comma_separated(self):
        html = 'aria-label="1,234 reviews"'
        m = self.REVIEWS_RE.search(html)
        assert m and m.group(1).replace(",", "") == "1234"

    def test_no_match_returns_none(self):
        html = '<div class="F7nice"><span>No rating</span></div>'
        assert self.STARS_RE.search(html) is None

    def test_full_f7nice_block(self):
        html = (
            '<div class="F7nice">'
            '<span class="ceNzKf" aria-label="4.9 stars "></span>'
            '<span role="img" aria-label="456 reviews"></span>'
            '</div>'
        )
        m_stars = self.STARS_RE.search(html)
        m_reviews = self.REVIEWS_RE.search(html)
        assert m_stars and m_stars.group(1) == "4.9"
        assert m_reviews and m_reviews.group(1) == "456"


class TestCoordinateRegex:
    """Test coordinate extraction from Google Maps URL."""

    COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")

    def test_standard_url(self):
        url = "https://www.google.com/maps/place/Plumber/@36.1699412,-115.1398296,17z"
        m = self.COORD_RE.search(url)
        assert m
        assert m.group(1) == "36.1699412"
        assert m.group(2) == "-115.1398296"

    def test_negative_lat(self):
        url = "https://www.google.com/maps/place/Shop/@-33.8688,151.2093,15z"
        m = self.COORD_RE.search(url)
        assert m
        assert m.group(1) == "-33.8688"

    def test_no_coords_returns_none(self):
        url = "https://www.google.com/maps/search/plumbers"
        assert self.COORD_RE.search(url) is None


class TestIsChromiumInstalled:
    def test_returns_bool(self):
        result = is_chromium_installed()
        assert isinstance(result, bool)

    def test_true_when_exe_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        exe_path = tmp_path / "AppData" / "Local" / "ms-playwright" / "chromium-1234" / "chrome-win64"
        exe_path.mkdir(parents=True)
        (exe_path / "chrome.exe").touch()
        assert is_chromium_installed() is True

    def test_false_when_no_exe(self, tmp_path, monkeypatch):
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        assert is_chromium_installed() is False
