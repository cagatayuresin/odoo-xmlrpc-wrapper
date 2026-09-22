"""List recent sales orders and displayed-row subtotals separated by currency."""

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from _common import iso_date, positive_limit, run_example, show_table


def configure(parser):
    parser.add_argument(
        "--since",
        type=iso_date,
        default=(datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat(),
        help="Inclusive YYYY-MM-DD in UTC; defaults to 30 days ago.",
    )
    parser.add_argument(
        "--state",
        choices=["all", "draft", "sent", "sale", "done", "cancel"],
        default="sale",
    )
    parser.add_argument(
        "--mine", action="store_true", help="Only orders assigned to you."
    )
    parser.add_argument("--limit", type=positive_limit, default=10)


def report(bot, args):
    model = "sale.order"
    domain = [("date_order", ">=", f"{args.since} 00:00:00")]
    if args.state != "all":
        domain.append(("state", "=", args.state))
    if args.mine:
        domain.append(("user_id", "=", bot.uid))
    total = bot.count(model, constraints=domain)
    print(f"Matching orders since {args.since} (UTC): {total}")
    if not total:
        print("No orders found. Try an earlier --since date or --state all.")
        return

    # custom() passes order= through to the standard, read-only search_read method.
    records = bot.custom(
        model,
        "search_read",
        att=[domain],
        kwargs={
            "fields": [
                "name",
                "partner_id",
                "date_order",
                "state",
                "amount_total",
                "currency_id",
            ],
            "limit": args.limit,
            "order": "date_order desc, id desc",
        },
    )
    print(f"Showing {len(records)} of {total} matching orders, newest first:")
    show_table(
        ["Order", "Customer", "Date (UTC)", "State", "Total incl. tax", "Currency"],
        [
            [
                row["name"],
                row.get("partner_id"),
                row.get("date_order"),
                row["state"],
                f"{row['amount_total']:,.2f}",
                row.get("currency_id"),
            ]
            for row in records
        ],
    )

    subtotals = {}
    for row in records:
        currency = row.get("currency_id")
        currency_id, label = currency if currency else (None, "Unknown currency")
        if currency_id not in subtotals:
            subtotals[currency_id] = [label, Decimal("0")]
        subtotals[currency_id][1] += Decimal(str(row["amount_total"]))
    if subtotals:
        print(
            "\nSubtotals for displayed orders only (including tax; no currency conversion):"
        )
        show_table(
            ["Currency", "Displayed subtotal"],
            [[label, f"{amount:,.2f}"] for label, amount in subtotals.values()],
        )


def main(argv=None):
    return run_example(__doc__, configure, report, argv)


if __name__ == "__main__":
    sys.exit(main())
