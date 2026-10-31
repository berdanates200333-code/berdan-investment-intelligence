"""Diagnose: Erreichbarkeit der Research-Quellen aus GitHub Actions (nur Statuscodes/Kurztexte)."""
import os
import re
import time

import requests

UA_SEC = os.environ.get("SEC_USER_AGENT") or "berdan-investment-intelligence research (berdanates200333-code@users.noreply.github.com)"
r = requests.get("https://data.sec.gov/submissions/CIK0000789019.json",
                 headers={"User-Agent": UA_SEC, "Accept-Encoding": "gzip, deflate"}, timeout=20)
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
print(f"SEC (Variable gesetzt: {bool(os.environ.get('SEC_USER_AGENT'))}): {r.status_code} :: {txt[:600]}")
try:
    ip = requests.get("https://api.ipify.org", timeout=10).text
    print("Runner-IP:", ip)
except Exception as e:  # noqa: BLE001
    print("IP unbekannt", e)

FEEDS = {
    "google_news_nvda": "https://news.google.com/rss/search?q=NVIDIA+when:2d&hl=en-US&gl=US&ceid=US:en",
    "yahoo_rss_nvda": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA&region=US&lang=en-US",
    "nvidia_newsroom": "https://nvidianews.nvidia.com/releases.xml",
    "nvidia_newsroom2": "https://nvidianews.nvidia.com/rss",
    "amd_ir": "https://ir.amd.com/news-events/press-releases/rss",
    "amd_newsroom": "https://www.amd.com/en/newsroom/press-releases.rss",
    "microsoft_news": "https://news.microsoft.com/feed/",
    "microsoft_ir": "https://www.microsoft.com/en-us/investor/rss",
    "gdelt": "https://api.gdeltproject.org/api/v2/doc/doc?query=Nvidia&mode=artlist&format=json&maxrecords=5&timespan=1d",
}
for k, u in FEEDS.items():
    try:
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0 (personal research script)"}, timeout=20)
        items = len(re.findall(r"<item>|<entry>", r.text))
        print(f"{k}: {r.status_code} {r.headers.get('content-type','')[:30]} items={items} {r.text[:80]!r}")
    except Exception as e:  # noqa: BLE001
        print(f"{k}: FEHLER {e}")
    time.sleep(1)
