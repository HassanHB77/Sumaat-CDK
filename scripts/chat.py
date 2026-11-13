"""Chat with the live Sumaat AI assistant from the terminal (demo / debugging; same route as the website panel).

Usage (from the project folder, after a deploy):
  SUMAAT_PASSWORD='...' uv run python scripts/chat.py omar@example.com     # asks for the password if not set

Type a message and press Enter. Commands:
  /new                new chat (the assistant forgets the conversation)
  /hofuf  /mubarraz   map spot the assistant searches from (default Al-Hofuf)
  /en  /ar            site language sent with each message (replies follow the language you type in)
  /quit
Every message uses 1 of the customer's 10 daily messages. Needs outputs.json (SumaatWeb.SiteUrl, SumaatAuth).
"""

import argparse
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so "python scripts/chat.py" can import the scripts package

from scripts.get_token import get_access_token  # noqa: E402
SPOTS = {"hofuf": (25.38, 49.588), "mubarraz": (25.41, 49.58)}
LANGS = ("en", "ar")
LABELS = {
    "find_restaurants": "finding restaurants",
    "search_dishes": "searching dishes",
    "get_menu": "reading a menu",
    "list_categories": "checking categories",
    "draft_cart": "preparing a cart draft",
}


def describe(event: dict) -> str | None:
    """What to print for one stream event (text pieces are printed as they come, so not here)."""
    kind = event.get("type")
    if kind == "status":
        return f"  ({LABELS.get(event.get('tool'), event.get('tool'))}...)"
    if kind == "quota":
        return f"  [{event['left']} messages left today]"
    if kind == "draft":
        lines = ", ".join(f"{line['qty']} x {line['name']}" for line in event["lines"])
        return (
            f"\n  [CART DRAFT from {event['restaurant']['name']}: {lines} = {event['totalHalalas'] / 100:.2f} SAR"
            " -> 'Add to cart' button on the website]"
        )
    if kind == "blocked":
        return "  [BLOCKED by the guardrail -> the website says: I can only help with food from Sumaat]"
    if kind == "error":
        return f"  [error: {event.get('code')}]"
    return None


def new_session() -> str:
    return "cli-" + uuid.uuid4().hex  # AgentCore needs at least 33 characters


def send(url: str, token: str, session: str, message: str, spot: tuple[float, float], lang: str) -> None:
    body = json.dumps({"message": message, "lat": spot[0], "lng": spot[1], "lang": lang}).encode()
    req = urllib.request.Request(
        url,
        method="POST",
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session,
        },
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            for raw in resp:
                line = raw.decode().strip()
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event.get("type") == "text":
                    print(event["delta"], end="", flush=True)
                elif (out := describe(event)) is not None:
                    print(out, flush=True)
    except urllib.error.HTTPError as err:
        print(f"  [HTTP {err.code}]")
    print(f"\n  ({time.time() - started:.1f} s)\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("email", nargs="?", default="sara@example.com", help="a customer account (default sara)")
    args = ap.parse_args()

    outputs = json.loads((ROOT / "outputs.json").read_text())
    url = outputs["SumaatWeb"]["SiteUrl"].rstrip("/") + "/agent/chat"
    password = os.environ.get("SUMAAT_PASSWORD") or getpass.getpass(f"Password for {args.email}: ", stream=sys.stderr)
    cognito = boto3.client("cognito-idp", region_name="us-east-1")
    try:
        token = get_access_token(cognito, outputs["SumaatAuth"]["UserPoolClientId"], args.email, password)
    except cognito.exceptions.NotAuthorizedException:
        sys.exit("Wrong email or password (or the user doesn't exist).")

    session, spot, lang = new_session(), SPOTS["hofuf"], "en"
    print(f"Logged in as {args.email}. Spot: hofuf, language: en. Commands: /new /hofuf /mubarraz /en /ar /quit\n")
    while True:
        try:
            msg = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg == "/quit":
            break
        if msg == "/new":
            session = new_session()
            print("  [new chat]\n")
        elif msg[1:] in SPOTS:
            spot = SPOTS[msg[1:]]
            print(f"  [spot: {msg[1:]}]\n")
        elif msg[1:] in LANGS:
            lang = msg[1:]
            print(f"  [language: {lang}]\n")
        elif msg:
            send(url, token, session, msg, spot, lang)


if __name__ == "__main__":
    main()
