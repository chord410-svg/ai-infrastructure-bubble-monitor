import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from src.http_client import fetch_bytes


class HttpClientTests(unittest.TestCase):
    @patch("src.http_client.urlopen")
    @patch("src.http_client.time.sleep")
    def test_retries_and_declares_identity(self, _sleep, mocked_open):
        response = MagicMock()
        response.read.return_value = b"ok"
        response.__enter__.return_value = response
        mocked_open.side_effect = [URLError("temporary"), response]

        self.assertEqual(fetch_bytes("https://example.test", attempts=2), b"ok")
        request = mocked_open.call_args.args[0]
        self.assertEqual(mocked_open.call_count, 2)
        self.assertIn("User-agent", request.headers)


if __name__ == "__main__":
    unittest.main()
