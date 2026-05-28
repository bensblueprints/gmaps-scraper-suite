"""Tests for shared/website_enricher.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from shared.website_enricher import (
    _detect_platform,
    _extract_emails,
    PLATFORM_SIGS,
    SKIP_DOMAINS,
    SKIP_PREFIXES,
    enrich,
)


# ── Platform detection ─────────────────────────────────────────────────────────

class TestDetectPlatform:
    def test_wordpress_wp_content(self):
        html = '<link rel="stylesheet" href="/wp-content/themes/mytheme/style.css">'
        assert _detect_platform(html, {}) == "WordPress"

    def test_wordpress_meta_generator(self):
        html = '<meta name="generator" content="WordPress 6.4"/>'
        assert _detect_platform(html, {}) == "WordPress"

    def test_shopify_cdn(self):
        html = '<script src="https://cdn.shopify.com/s/files/1/0/app.js"></script>'
        assert _detect_platform(html, {}) == "Shopify"

    def test_wix_static(self):
        html = '<img src="https://static.wixstatic.com/media/logo.png"/>'
        assert _detect_platform(html, {}) == "Wix"

    def test_squarespace(self):
        html = '<script src="https://static1.squarespace.com/static/main.js"></script>'
        assert _detect_platform(html, {}) == "Squarespace"

    def test_webflow(self):
        html = '<html data-wf-site="abc123">'
        assert _detect_platform(html, {}) == "Webflow"

    def test_hubspot(self):
        html = '<script src="https://js.hs-scripts.com/123456.js"></script>'
        assert _detect_platform(html, {}) == "HubSpot"

    def test_elementor(self):
        html = '<link rel="stylesheet" href="/wp-content/plugins/elementor/assets/css/frontend.css">'
        assert _detect_platform(html, {}) in ("WordPress", "Elementor")

    def test_unknown_platform(self):
        html = '<html><body><p>Hello world</p></body></html>'
        assert _detect_platform(html, {}) == ""

    def test_header_detection(self):
        html = ""
        headers = {"X-Wix-Published-Version": "12345"}
        assert _detect_platform(html, headers) == "Wix"

    def test_case_insensitive(self):
        html = '/WP-CONTENT/themes/test/'
        assert _detect_platform(html, {}) == "WordPress"

    def test_godaddy(self):
        html = '<script src="https://img1.wsimg.com/blobby/go/build.js"></script>'
        # GoDaddy uses secureserver.net or myftpupload
        html2 = 'myftpupload.com/wp-content'
        assert _detect_platform(html2, {}) == "GoDaddy"


# ── Email extraction ───────────────────────────────────────────────────────────

class TestExtractEmails:
    def test_simple_email(self):
        html = 'Contact us at info@mybusiness.com for help.'
        emails = _extract_emails(html, 'mybusiness.com')
        assert 'info@mybusiness.com' in emails

    def test_multiple_emails(self):
        html = 'Email us: sales@acme.com or support@acme.com'
        emails = _extract_emails(html, 'acme.com')
        assert len(emails) == 2
        assert 'sales@acme.com' in emails
        assert 'support@acme.com' in emails

    def test_max_5_per_page(self):
        html = ' '.join(f'user{i}@business.com' for i in range(10))
        emails = _extract_emails(html, 'business.com')
        assert len(emails) <= 5

    def test_skip_domain_google(self):
        html = 'See google.com@google.com or test@google.com'
        emails = _extract_emails(html, 'mybiz.com')
        assert not any('google.com' in e for e in emails)

    def test_skip_domain_facebook(self):
        html = 'Like us on fb: admin@facebook.com'
        emails = _extract_emails(html, 'mybiz.com')
        assert 'admin@facebook.com' not in emails

    def test_skip_noreply(self):
        html = 'noreply@mybusiness.com'
        emails = _extract_emails(html, 'mybusiness.com')
        assert 'noreply@mybusiness.com' not in emails

    def test_skip_no_reply_hyphen(self):
        html = 'no-reply@mybusiness.com'
        emails = _extract_emails(html, 'mybusiness.com')
        assert 'no-reply@mybusiness.com' not in emails

    def test_skip_image_extensions(self):
        html = 'Background: contact@image.png, real@biz.com'
        emails = _extract_emails(html, 'biz.com')
        assert 'contact@image.png' not in emails
        assert 'real@biz.com' in emails

    def test_domain_match_sorted_first(self):
        html = 'other@other.com or owner@mybiz.com'
        emails = _extract_emails(html, 'mybiz.com')
        assert emails[0] == 'owner@mybiz.com'

    def test_deduplicate(self):
        html = 'info@biz.com info@biz.com info@biz.com'
        emails = _extract_emails(html, 'biz.com')
        assert emails.count('info@biz.com') == 1

    def test_lowercase_normalisation(self):
        html = 'INFO@BIZ.COM'
        emails = _extract_emails(html, 'biz.com')
        assert 'info@biz.com' in emails

    def test_strip_trailing_punctuation(self):
        html = '"info@biz.com"'
        emails = _extract_emails(html, 'biz.com')
        assert 'info@biz.com' in emails

    def test_skip_wixpress(self):
        html = 'admin@wixpress.com'
        emails = _extract_emails(html, 'mybiz.com')
        assert 'admin@wixpress.com' not in emails

    def test_skip_latofonts(self):
        html = 'team@latofonts.com'
        emails = _extract_emails(html, 'mybiz.com')
        assert 'team@latofonts.com' not in emails

    def test_empty_html(self):
        assert _extract_emails('', 'biz.com') == []


# ── enrich() integration (mocked HTTP) ────────────────────────────────────────

class TestEnrich:
    def _mock_session(self, homepage_html, contact_html=None):
        session = MagicMock()
        homepage_resp = MagicMock()
        homepage_resp.status_code = 200
        homepage_resp.headers = {'Content-Type': 'text/html'}
        homepage_resp.text = homepage_html

        if contact_html is not None:
            contact_resp = MagicMock()
            contact_resp.status_code = 200
            contact_resp.headers = {'Content-Type': 'text/html'}
            contact_resp.text = contact_html
            session.get.side_effect = [homepage_resp, contact_resp]
        else:
            session.get.return_value = homepage_resp

        return session

    def test_returns_dict_keys(self):
        result = enrich('')
        assert set(result.keys()) == {'platform', 'emails', 'contact_url', 'error'}

    def test_empty_url_returns_empty(self):
        result = enrich('')
        assert result['emails'] == []
        assert result['platform'] == ''

    def test_finds_email_on_homepage(self):
        html = '<html><body>Call or email: hello@testco.com</body></html>'
        with patch('shared.website_enricher._make_session') as mock_sess:
            sess = self._mock_session(html)
            mock_sess.return_value = sess
            result = enrich('https://testco.com')
        assert 'hello@testco.com' in result['emails']
        assert result['contact_url'] == 'https://testco.com'

    def test_detects_wordpress_platform(self):
        html = '<html><head><link href="/wp-content/themes/x/style.css"></head></html>'
        with patch('shared.website_enricher._make_session') as mock_sess:
            sess = self._mock_session(html)
            mock_sess.return_value = sess
            result = enrich('https://wpsite.com')
        assert result['platform'] == 'WordPress'

    def test_unreachable_returns_error(self):
        with patch('shared.website_enricher._make_session') as mock_sess:
            sess = MagicMock()
            sess.get.side_effect = Exception("Connection refused")
            mock_sess.return_value = sess
            result = enrich('https://unreachable-site-xyz.com')
        assert result['error'] == 'unreachable'

    def test_normalises_url_without_scheme(self):
        html = '<html><body>Email: owner@shop.com</body></html>'
        with patch('shared.website_enricher._make_session') as mock_sess:
            sess = self._mock_session(html)
            mock_sess.return_value = sess
            result = enrich('shop.com')
        assert 'owner@shop.com' in result['emails']

    def test_falls_through_to_contact_page(self):
        homepage = '<html><body>No email here, just a website.</body></html>'
        contact = '<html><body>Contact: reach@contactbiz.com</body></html>'
        with patch('shared.website_enricher._make_session') as mock_sess:
            sess = MagicMock()
            homepage_resp = MagicMock(status_code=200,
                                      headers={'Content-Type': 'text/html'},
                                      text=homepage)
            contact_resp = MagicMock(status_code=200,
                                     headers={'Content-Type': 'text/html'},
                                     text=contact)
            sess.get.side_effect = [homepage_resp, contact_resp]
            mock_sess.return_value = sess
            result = enrich('https://contactbiz.com')
        assert 'reach@contactbiz.com' in result['emails']
        assert 'contact' in result['contact_url']
