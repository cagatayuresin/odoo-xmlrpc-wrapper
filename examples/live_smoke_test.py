"""Manually exercise read operations against a real Odoo XML-RPC endpoint."""

import argparse
import getpass
import sys
import warnings
from xmlrpc.client import Fault, ProtocolError

from defusedxml.common import DefusedXmlException

from odoo_xmlrpc_wrapper import Bot, __version__


def check(condition, operation):
    if not condition:
        raise ValueError(f"Unexpected result from {operation}")
    print(f"PASS {operation}")


def run_checks(bot):
    """Read only the authenticated user's record; never call CRUD writes."""
    model = "res.users"
    domain = [("id", "=", bot.uid)]
    print("PASS authentication")
    print(f"Odoo version: {bot.version.get('server_version', 'unknown')}")

    records = bot.read(model, ids=[bot.uid], fields=["name"])
    check(len(records) == 1 and records[0]["id"] == bot.uid, "read")

    ids = bot.search(model, constraints=domain, offset=0, limit=1)
    check(ids == [bot.uid], "search")

    records = bot.search_read(model, constraints=domain, fields=["name"], limit=1)
    check(len(records) == 1 and records[0]["id"] == bot.uid, "search_read")

    check(bot.count(model, constraints=domain) == 1, "count")
    fields = bot.get_fields(model, attributes=["type"])
    check(fields.get("name", {}).get("type") == "char", "get_fields")

    count = bot.custom(model, "search_count", att=[domain], kwargs={})
    check(count == 1, "custom (search_count)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--http", action="store_true", help="Explicitly use unencrypted HTTP."
    )
    parser.add_argument("--timeout", type=float, default=30, help="Socket timeout.")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        parser.error("Run this script in an interactive terminal; do not pipe secrets.")

    print(f"odoo-xmlrpc-wrapper: {__version__}")
    print("This test does not create, update, or delete business records.")
    if args.http:
        print("HTTP selected: credentials will travel without TLS encryption.")
    stage = "configuration"
    try:
        host = input("Odoo host (e.g. odoo.example.com): ").strip()
        db = input("Database name: ").strip()
        username = input("Login / email: ").strip()
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password / API key (hidden): ")
        stage = "connection / authentication"
        with Bot(
            host=host,
            db=db,
            userlogin=username,
            password=password,
            secured=not args.http,
            timeout=args.timeout,
        ) as bot:
            stage = "read checks (last PASS above identifies progress)"
            run_checks(bot)
        print("PASS connection cleanup")
        print("SUCCESS: all live read checks passed.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        return 130
    except getpass.GetPassWarning:
        print("FAIL: this terminal cannot hide password input.", file=sys.stderr)
    except PermissionError:
        print(
            "FAIL authentication: check the database, login and API key.",
            file=sys.stderr,
        )
    except Fault:
        print(
            f"FAIL {stage}: Odoo returned an XML-RPC fault. Check the user's API "
            "and model permissions. Server details were omitted from this report.",
            file=sys.stderr,
        )
    except ProtocolError as error:
        print(f"FAIL {stage}: HTTP status {error.errcode}.", file=sys.stderr)
    except (OSError, ValueError, DefusedXmlException) as error:
        print(f"FAIL {stage}: {type(error).__name__}.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
