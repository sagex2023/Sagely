"""Push the rendered issue to Buttondown as a DRAFT (default) or scheduled send.

Env: BUTTONDOWN_API_KEY. Untested against the live API in the build sandbox (network blocked);
check the response once from your machine. Draft mode keeps you in the loop: review on your phone,
click send. That 5-minute review is also what keeps the publication clearly impersonal/general.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path


def push_draft(subject: str, html_path: Path, status: str = "draft") -> dict:
    key = os.environ["BUTTONDOWN_API_KEY"]
    body = html_path.read_text()
    req = urllib.request.Request(
        "https://api.buttondown.com/v1/emails",
        data=json.dumps({"subject": subject, "body": body, "status": status}).encode(),
        headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())
