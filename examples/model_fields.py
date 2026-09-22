"""Inspect readable Odoo field metadata before building your own queries."""

import sys

from _common import positive_limit, run_example, show_table


def configure(parser):
    """Add model and field filters to the shared connection options."""
    parser.add_argument(
        "--model", default="crm.lead", help="Technical model name (default: crm.lead)."
    )
    parser.add_argument(
        "--query", default="", help="Match part of a field name or label."
    )
    parser.add_argument(
        "--limit", type=positive_limit, default=30, help="Rows to display (1-100)."
    )


def report(bot, args):
    """Read field metadata and display matching fields in name order."""
    fields = bot.get_fields(
        args.model, attributes=["string", "type", "required", "readonly", "relation"]
    )
    query = args.query.casefold()
    matches = [
        (name, metadata)
        for name, metadata in sorted(fields.items())
        if query in name.casefold()
        or query in str(metadata.get("string") or "").casefold()
    ]
    selected = matches[: args.limit]
    print(f"Matching fields: {len(matches)}; displayed: {len(selected)}.")
    if not selected:
        print("No accessible fields match this filter.")
        return

    show_table(
        ["Field", "Label", "Type", "Required", "Readonly", "Relation"],
        [
            [
                name,
                metadata.get("string"),
                metadata.get("type"),
                "Yes" if metadata.get("required") else "No",
                "Yes" if metadata.get("readonly") else "No",
                metadata.get("relation"),
            ]
            for name, metadata in selected
        ],
    )


def main(argv=None):
    return run_example(__doc__, configure, report, argv)


if __name__ == "__main__":
    sys.exit(main())
