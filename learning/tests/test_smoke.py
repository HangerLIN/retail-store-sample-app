import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import smoke


class SmokeTests(unittest.TestCase):
    def order(self, id="new", marker="smoke-test"):
        return {"id": id, "shippingAddress": {"firstName": marker, "email": marker + "@example.invalid"}}

    def test_matching_order(self):
        smoke.verify_order([self.order("old"), self.order()], "new", "smoke-test")

    def test_marker_in_different_order_rejected(self):
        with self.assertRaises(AssertionError):
            smoke.verify_order([self.order(marker="wrong"), self.order("old")], "new", "smoke-test")

    def test_missing_duplicate_malformed_order_rejected(self):
        for payload in ([], [self.order(), self.order()], {}, [{"id": "new"}]):
            with self.subTest(payload=payload), self.assertRaises(AssertionError):
                smoke.verify_order(payload, "new", "smoke-test")

    def test_bounded_json_response(self):
        with patch.object(smoke.urllib.request, "urlopen", return_value=io.BytesIO(b'[]')) as fetch:
            self.assertEqual(smoke.getjson("http://test"), [])
            fetch.assert_called_once_with("http://test", timeout=25)
        with patch.object(smoke, "MAX_JSON_BYTES", 3), patch.object(smoke.urllib.request, "urlopen", return_value=io.BytesIO(b'[1,2]')):
            with self.assertRaisesRegex(AssertionError, "limit"):
                smoke.getjson("http://test")


if __name__ == "__main__":
    unittest.main()
