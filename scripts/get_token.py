"""Print a Cognito ID token for testing the deployed API from the terminal.

Usage:
  TOKEN=$(uv run python scripts/get_token.py owner.nakhla@example.com)    # asks for the password
  SUMAAT_PASSWORD='...' uv run python scripts/get_token.py someone@example.com
  curl -H "Authorization: $TOKEN" "$API/..."

Prints ONLY the ID token on stdout (prompts and errors go to stderr), so it works inside $( ).
The ID token carries name, groups and custom:restaurantId, which the API reads.
"""

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parent.parent


def get_id_token(cognito, client_id: str, email: str, password: str) -> str:
    resp = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    if "AuthenticationResult" not in resp:
        raise RuntimeError(f"Login needs an extra step: {resp.get('ChallengeName')}")
    return resp["AuthenticationResult"]["IdToken"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("email")
    ap.add_argument("--client-id", help="default: SumaatAuth.UserPoolClientId from outputs.json")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    client_id = args.client_id or json.loads((ROOT / "outputs.json").read_text())["SumaatAuth"]["UserPoolClientId"]
    password = os.environ.get("SUMAAT_PASSWORD") or getpass.getpass(f"Password for {args.email}: ", stream=sys.stderr)
    cognito = boto3.client("cognito-idp", region_name=args.region)
    try:
        print(get_id_token(cognito, client_id, args.email, password))
    except cognito.exceptions.NotAuthorizedException:
        sys.exit("Wrong email or password (or the user doesn't exist).")
    except cognito.exceptions.UserNotConfirmedException:
        sys.exit("Email not confirmed yet: enter the code from the sign-up email first.")


if __name__ == "__main__":
    main()
