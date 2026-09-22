"""Search active contacts and companies without changing business records."""

import sys

from _common import positive_limit, run_example, show_table


def configure(parser):
    """Add contact filters to the shared connection options."""
    parser.add_argument("--query", default="", help="Match part of a contact name.")
    parser.add_argument(
        "--companies", action="store_true", help="Show only company contacts."
    )
    parser.add_argument(
        "--limit", type=positive_limit, default=10, help="Rows to display (1-100)."
    )


def report(bot, args):
    """Count matching contacts and display a limited set of selected fields."""
    domain = [("active", "=", True)]
    if args.query:
        domain.append(("name", "ilike", args.query))
    if args.companies:
        domain.append(("is_company", "=", True))

    total = bot.count("res.partner", constraints=domain)
    records = bot.search_read(
        "res.partner",
        constraints=domain,
        fields=["name", "is_company", "city", "country_id"],
        limit=args.limit,
    )
    print(f"Matching contacts: {total}; displayed: {len(records)}.")
    if not records:
        print("No active contacts match these filters within your access rights.")
        return

    show_table(
        ["ID", "Name", "Company", "City", "Country"],
        [
            [
                record["id"],
                record.get("name"),
                "Yes" if record.get("is_company") else "No",
                record.get("city"),
                record.get("country_id"),
            ]
            for record in records
        ],
    )


def main(argv=None):
    return run_example(__doc__, configure, report, argv)


if __name__ == "__main__":
    sys.exit(main())
