"""Show open CRM opportunities and server-side opportunity counts by stage."""

import sys

from _common import positive_limit, run_example, show_table


def configure(parser):
    parser.add_argument(
        "--mine", action="store_true", help="Only opportunities assigned to you."
    )
    parser.add_argument("--limit", type=positive_limit, default=15)


def report(bot, args):
    model = "crm.lead"
    domain = [
        ("active", "=", True),
        ("type", "=", "opportunity"),
        ("stage_id.is_won", "=", False),
    ]
    if args.mine:
        domain.append(("user_id", "=", bot.uid))
    total = bot.count(model, constraints=domain)
    print(f"Open opportunities matching the filter: {total}")
    if not total:
        print("No open opportunities found for this filter.")
        return

    # read_group is an Odoo read operation; no business action is triggered.
    groups = bot.custom(
        model,
        "read_group",
        att=[domain, ["stage_id"], ["stage_id"]],
        kwargs={"lazy": False, "limit": args.limit},
    )
    print(
        f"Stage counts (up to {args.limit} stages; each count covers the full filter):"
    )
    show_table(
        ["Stage", "Opportunities"],
        [[group.get("stage_id"), group["__count"]] for group in groups],
    )

    records = bot.search_read(
        model,
        constraints=domain,
        fields=[
            "name",
            "stage_id",
            "user_id",
            "expected_revenue",
            "company_currency",
            "probability",
        ],
        limit=args.limit,
    )
    print(
        f"\nShowing {len(records)} of {total} matching opportunities (Odoo's default order):"
    )
    show_table(
        [
            "ID",
            "Opportunity",
            "Stage",
            "Salesperson",
            "Expected revenue",
            "Currency",
            "Probability %",
        ],
        [
            [
                row["id"],
                row["name"],
                row.get("stage_id"),
                row.get("user_id"),
                f"{row.get('expected_revenue', 0):,.2f}",
                row.get("company_currency"),
                row.get("probability", 0),
            ]
            for row in records
        ],
    )


def main(argv=None):
    return run_example(__doc__, configure, report, argv)


if __name__ == "__main__":
    sys.exit(main())
