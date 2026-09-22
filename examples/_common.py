"""Shared terminal setup for the manual, read-only examples."""

import argparse
import getpass
import math
import os
import re
import sys
import warnings
from datetime import date
from xmlrpc.client import Fault, ProtocolError

from defusedxml.common import DefusedXmlException

from odoo_xmlrpc_wrapper import Bot, __version__


def positive_limit(value):
    """Keep example queries and their terminal output bounded."""
    try:
        limit = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "limit must be an integer from 1 to 100"
        ) from None
    if not 1 <= limit <= 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return limit


def positive_timeout(value):
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("timeout must be a positive number") from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be finite and positive")
    return timeout


def iso_date(value):
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError("date must be valid YYYY-MM-DD") from None


def display(value):
    """Render Odoo values without allowing record text to control the terminal."""
    if value is None or value is False:
        return "-"
    if isinstance(value, (list, tuple)) and len(value) == 2:
        value = value[1]  # Odoo many2one: [record_id, display_name].
    return "".join(
        char if char.isprintable() else f"\\u{ord(char):04x}" for char in str(value)
    )


def show_table(headers, rows):
    cells = [[display(value) for value in row] for row in [headers, *rows]]
    cells = [
        [cell if len(cell) <= 40 else cell[:37] + "..." for cell in row]
        for row in cells
    ]
    widths = [max(len(row[column]) for row in cells) for column in range(len(headers))]
    for index, row in enumerate(cells):
        print(
            " | ".join(
                cell.ljust(width) for cell, width in zip(row, widths, strict=True)
            )
        )
        if index == 0:
            print("-+-".join("-" * width for width in widths))


def run_example(description, configure, report, argv=None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--host",
        default=os.environ.get("ODOO_HOST"),
        help="Host; defaults to ODOO_HOST or a prompt.",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("ODOO_DB"),
        help="Database; defaults to ODOO_DB or a prompt.",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("ODOO_USERNAME"),
        help="Login; defaults to ODOO_USERNAME or a prompt.",
    )
    parser.add_argument("--http", action="store_true", help="Use unencrypted HTTP.")
    parser.add_argument(
        "--timeout",
        type=positive_timeout,
        default=30.0,
        help="Socket timeout in seconds (default: 30).",
    )
    configure(parser)
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        parser.error("Run in an interactive terminal so the password can be hidden.")

    print(f"odoo-xmlrpc-wrapper: {__version__}")
    print("This example only calls read methods; it does not modify business records.")
    if args.http:
        print("HTTP selected: credentials will travel without TLS encryption.")
    stage = "configuration"
    try:
        host = args.host or input("Odoo host (e.g. odoo.example.com): ").strip()
        db = args.db or input("Database name: ").strip()
        user = args.user or input("Login / email: ").strip()
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password / API key (hidden): ")
        stage = "connection / authentication"
        with Bot(
            host=host,
            db=db,
            userlogin=user,
            password=password,
            secured=not args.http,
            timeout=args.timeout,
        ) as bot:
            stage = "report"
            report(bot, args)
        print("Done. Connection closed.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        return 130
    except getpass.GetPassWarning:
        print("FAIL: this terminal cannot hide password input.", file=sys.stderr)
    except PermissionError:
        print(
            "FAIL authentication: check database, login and API key.", file=sys.stderr
        )
    except Fault:
        print(
            f"FAIL {stage}: Odoo XML-RPC fault. Check that the requested module is "
            "installed and the account can read its models and fields. "
            "Server error details were omitted.",
            file=sys.stderr,
        )
    except ProtocolError as error:
        print(f"FAIL {stage}: HTTP status {error.errcode}.", file=sys.stderr)
    except (OSError, ValueError, DefusedXmlException) as error:
        print(f"FAIL {stage}: {type(error).__name__}.", file=sys.stderr)
    return 1
