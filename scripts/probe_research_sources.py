"""Diagnose: Welche User-Agent-Varianten akzeptiert SEC EDGAR, und antwortet GDELT? (nur Statuscodes)"""
import os
import time

import requests

URL = "https://data.sec.gov/submissions/CIK0000789019.json"
UAS = {
    "projekt_klammer": "berdan-investment-intelligence research (berdanates200333-code@users.noreply.github.com)",
    "name_email": "BerdanInvestmentIntelligence berdanates200333-code@users.noreply.github.com",
    "person_email": "Berdan Ates berdanates200333-code@users.noreply.github.com",
    "variable": os.environ.get("SEC_USER_AGENT") or "",
}
for k, ua in UAS.items():
    if not ua:
        print(f"{k}: (nicht gesetzt)")
        continue
    for host_hdr in (False, True):
        h = {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}
        if host_hdr:
            h["Host"] = "data.sec.gov"
        r = requests.get(URL, headers=h, timeout=20)
        print(f"SEC {k} host={host_hdr}: {r.status_code} {r.headers.get('content-type','')[:30]} {r.text[:120]!r}")
        time.sleep(0.5)
r = requests.get("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom",
                 headers={"User-Agent": UAS["person_email"]}, timeout=20)
print("SEC atom www:", r.status_code)
for q in ["Microsoft", "(Nvidia OR NVDA) sourcelang:english"]:
    for wait in (0, 15):
        time.sleep(wait)
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                         params={"query": q, "mode": "artlist", "format": "json", "maxrecords": 10, "timespan": "2d"},
                         headers={"User-Agent": "Mozilla/5.0 (personal research script)"}, timeout=30)
        print(f"GDELT {q!r} wait={wait}: {r.status_code} {r.text[:150]!r}")
