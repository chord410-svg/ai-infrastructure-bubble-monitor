import os
import time
from urllib.request import Request, urlopen


DEFAULT_AGENT = "ai-bubble-monitor/1.0 maintainer@example.invalid"


def fetch_bytes(url, *, attempts=3, timeout=30):
    agent = os.environ.get("SEC_USER_AGENT", DEFAULT_AGENT)
    last_error = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": agent, "Accept": "*/*"})
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise last_error
