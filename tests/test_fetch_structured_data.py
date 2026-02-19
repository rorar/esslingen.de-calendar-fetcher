import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from app import fetch_structured_data


class TestFetchStructuredData(unittest.TestCase):
    def test_build_json_url_with_category_filters(self) -> None:
        url = fetch_structured_data.build_json_url(
            series_id="330100",
            anz="-1",
            cat_ids=["908119", "908120"],
            ldx="123456",
        )
        qs = parse_qs(urlparse(url).query)

        self.assertEqual(qs["q.sammelbegrif.id"], ["330100"])
        self.assertEqual(qs["anz"], ["-1"])
        self.assertEqual(qs["ldx"], ["123456"])
        self.assertEqual(qs["q.kat.id"], ["908119", "908120"])

    def test_merge_event_lists_deduplicates_by_id(self) -> None:
        a = [{"id": "1", "titel": "A"}, {"id": "2", "titel": "B"}]
        b = [{"id": "2", "titel": "B2"}, {"id": "3", "titel": "C"}]

        merged = fetch_structured_data.merge_event_lists([a, b])
        self.assertEqual([str(item["id"]) for item in merged], ["1", "2", "3"])

    def test_merge_event_lists_deduplicates_without_id_by_fallback_key(self) -> None:
        a = [{"titel": "Ohne ID", "von": "10.03.2026", "zeit": "18:00", "location": "Ort"}]
        b = [{"titel": "Ohne ID", "von": "10.03.2026", "zeit": "18:00", "location": "Ort"}]

        merged = fetch_structured_data.merge_event_lists([a, b])
        self.assertEqual(len(merged), 1)

    @patch("app.fetch_structured_data.has_stealth_requests", return_value=True)
    @patch("app.fetch_structured_data.has_curl", return_value=True)
    def test_resolve_backend_order_auto_prefers_stealth_then_curl(self, _curl: object, _stealth: object) -> None:
        order = fetch_structured_data.resolve_backend_order("auto")
        self.assertEqual(order, ["stealth-requests", "curl", "urllib"])

    @patch("app.fetch_structured_data.has_curl", return_value=True)
    def test_resolve_backend_order_explicit_stealth_keeps_fallbacks(self, _curl: object) -> None:
        order = fetch_structured_data.resolve_backend_order("stealth")
        self.assertEqual(order, ["stealth-requests", "curl", "urllib"])

    def test_resolve_backend_order_explicit_curl_keeps_urllib_fallback(self) -> None:
        order = fetch_structured_data.resolve_backend_order("curl")
        self.assertEqual(order, ["curl", "urllib"])

    def test_resolve_backend_order_explicit_urllib_is_single_backend(self) -> None:
        order = fetch_structured_data.resolve_backend_order("urllib")
        self.assertEqual(order, ["urllib"])


if __name__ == "__main__":
    unittest.main()
