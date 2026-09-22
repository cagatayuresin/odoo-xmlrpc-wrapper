"""Offline checks for bounded, read-only examples and safe terminal input."""

import contextlib
import importlib
import importlib.util
import io
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch
from xmlrpc.client import Fault

from odoo_xmlrpc_wrapper import Bot

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def load_example(name):
    spec = importlib.util.spec_from_file_location(name, _EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Keep the package import above pointing to the installed wheel under Python -I.
with patch.object(sys, "path", [str(_EXAMPLES), *sys.path]):
    common = importlib.import_module("_common")
    examples = {
        name: load_example(name)
        for name in ("contacts", "crm_pipeline", "sales_orders", "model_fields")
    }


class ReadExamplesTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.stdout = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.stdin = stack.enter_context(patch.object(common.sys, "stdin"))
        self.stdin.isatty.return_value = True
        stack.enter_context(
            patch.dict(
                "os.environ", {"ODOO_HOST": "", "ODOO_DB": "", "ODOO_USERNAME": ""}
            )
        )
        self.input = stack.enter_context(
            patch(
                "builtins.input",
                side_effect=["odoo.example.test", "crm", "login"] * len(examples),
            )
        )
        self.secret = "private-example-api-key"
        self.getpass = stack.enter_context(
            patch.object(common.getpass, "getpass", return_value=self.secret)
        )
        self.bot = MagicMock(spec=Bot)
        self.bot.uid = 7
        self.bot.version = {"server_version": "16.0"}
        self.bot.__enter__.return_value = self.bot
        self.bot.__exit__.return_value = False
        self.bot.count.return_value = 0
        self.bot.search_read.return_value = []
        self.bot.get_fields.return_value = {}
        self.bot.custom.return_value = []
        self.factory = stack.enter_context(
            patch.object(common, "Bot", return_value=self.bot)
        )

    def assert_read_only(self):
        for name, args, kwargs in self.bot.method_calls:
            self.assertIn(name, {"count", "search_read", "get_fields", "custom"})
            if name == "custom":
                command = args[1] if len(args) > 1 else kwargs.get("command")
                self.assertIn(command, {"read_group", "search_read"})
                options = kwargs.get("kwargs", args[3] if len(args) > 3 else {})
                self.assertGreater(options["limit"], 0)
                self.assertLessEqual(options["limit"], 100)
            if name == "search_read":
                self.assertGreater(kwargs["limit"], 0)
                self.assertLessEqual(kwargs["limit"], 100)

    def test_empty_results_succeed_using_only_read_operations(self):
        for name, example in examples.items():
            with self.subTest(example=name):
                self.bot.reset_mock()
                self.assertEqual(example.main([]), 0)
                self.assertTrue(self.bot.method_calls)
                self.assert_read_only()
                self.bot.__exit__.assert_called_once_with(None, None, None)
        self.assertNotIn(self.secret, self.stdout.getvalue() + self.stderr.getvalue())
        self.assertEqual(self.stderr.getvalue(), "")
        self.factory.assert_called_with(
            host="odoo.example.test",
            db="crm",
            userlogin="login",
            password=self.secret,
            secured=True,
            timeout=30,
        )

    def test_unbounded_or_invalid_limits_fail_before_credentials_or_connection(self):
        for name, example in examples.items():
            for limit in ("0", "-1", "101"):
                with self.subTest(example=name, limit=limit):
                    with self.assertRaises(SystemExit) as error:
                        example.main(["--limit", limit])
                    self.assertEqual(error.exception.code, 2)
        self.input.assert_not_called()
        self.getpass.assert_not_called()
        self.factory.assert_not_called()

    def test_invalid_dates_and_timeouts_fail_before_connection(self):
        for value in ("2025-02-30", "2026-1-1", "yesterday"):
            with self.subTest(date=value):
                with self.assertRaises(SystemExit) as error:
                    examples["sales_orders"].main(["--since", value])
                self.assertEqual(error.exception.code, 2)
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(timeout=value):
                with self.assertRaises(SystemExit) as error:
                    examples["contacts"].main(["--timeout", value])
                self.assertEqual(error.exception.code, 2)
        self.input.assert_not_called()
        self.getpass.assert_not_called()
        self.factory.assert_not_called()

    def test_noninteractive_input_fails_before_reading_secrets(self):
        self.stdin.isatty.return_value = False
        with self.assertRaises(SystemExit) as error:
            examples["contacts"].main([])
        self.assertEqual(error.exception.code, 2)
        self.input.assert_not_called()
        self.getpass.assert_not_called()
        self.factory.assert_not_called()

    def test_connection_flags_skip_prompts_but_password_stays_hidden(self):
        self.assertEqual(
            examples["contacts"].main(
                ["--host", "odoo.example.test", "--db", "crm", "--user", "login"]
            ),
            0,
        )
        self.input.assert_not_called()
        self.getpass.assert_called_once_with("Password / API key (hidden): ")
        self.assertEqual(self.factory.call_args.kwargs["password"], self.secret)
        self.assertTrue(self.factory.call_args.kwargs["secured"])
        self.assertNotIn(self.secret, self.stdout.getvalue() + self.stderr.getvalue())

    def test_getpass_fallback_stops_before_secret_can_be_echoed(self):
        def insecure_fallback(prompt):
            warnings.warn(
                "Cannot hide input", common.getpass.GetPassWarning, stacklevel=2
            )
            self.fail("Password fallback must not read an echoed secret")

        self.getpass.side_effect = insecure_fallback
        self.assertEqual(examples["contacts"].main([]), 1)
        self.factory.assert_not_called()
        self.assertNotIn(self.secret, self.stdout.getvalue() + self.stderr.getvalue())

    def test_rpc_fault_omits_server_details_and_closes_connection(self):
        self.bot.count.side_effect = Fault(
            1, f"Server traceback contains {self.secret} and confidential-marker"
        )
        self.assertEqual(examples["contacts"].main([]), 1)
        self.assertIn("XML-RPC fault", self.stderr.getvalue())
        for hidden in (self.secret, "Server traceback", "confidential-marker"):
            self.assertNotIn(hidden, self.stdout.getvalue() + self.stderr.getvalue())
        self.bot.__exit__.assert_called_once()
        self.assert_read_only()

    def test_server_values_cannot_inject_terminal_control_sequences(self):
        common.show_table(["Name"], [["ok\x1b\r\n\x07\u202eevil"]])
        output = self.stdout.getvalue()
        for control in ("\x1b", "\r", "\x07", "\u202e"):
            self.assertNotIn(control, output)
        self.assertIn("ok", output)
        self.assertIn("evil", output)

    def test_contact_filters_apply_to_count_and_bounded_read(self):
        self.bot.count.return_value = 20
        self.bot.search_read.return_value = [
            {
                "id": 3,
                "name": "A&B Example",
                "is_company": True,
                "city": False,
                "country_id": [1, "Türkiye"],
            }
        ]
        self.assertEqual(
            examples["contacts"].main(
                ["--query", "A&B", "--companies", "--limit", "2"]
            ),
            0,
        )
        domain = [
            ("active", "=", True),
            ("name", "ilike", "A&B"),
            ("is_company", "=", True),
        ]
        self.bot.count.assert_called_once_with("res.partner", constraints=domain)
        read = self.bot.search_read.call_args
        self.assertEqual(read.args, ("res.partner",))
        self.assertEqual(read.kwargs["constraints"], domain)
        self.assertEqual(read.kwargs["limit"], 2)
        self.assertNotIn("email", read.kwargs["fields"])
        self.assertNotIn("phone", read.kwargs["fields"])
        self.assertIn("A&B Example", self.stdout.getvalue())
        self.assertIn("Türkiye", self.stdout.getvalue())
        self.assert_read_only()

    def test_crm_personal_filter_matches_stage_counts_and_read_domain(self):
        self.bot.count.return_value = 20
        self.bot.custom.return_value = [{"stage_id": [4, "Qualified"], "__count": 20}]
        self.bot.search_read.return_value = [
            {
                "id": 5,
                "name": "Example deal",
                "stage_id": [4, "Qualified"],
                "user_id": [7, "Current User"],
                "expected_revenue": 1000,
                "company_currency": [1, "USD"],
                "probability": 40,
            }
        ]
        self.assertEqual(examples["crm_pipeline"].main(["--mine", "--limit", "2"]), 0)
        domain = self.bot.count.call_args.kwargs["constraints"]
        for condition in (
            ("active", "=", True),
            ("type", "=", "opportunity"),
            ("stage_id.is_won", "=", False),
            ("user_id", "=", 7),
        ):
            self.assertIn(condition, domain)
        grouped = self.bot.custom.call_args
        self.assertEqual(grouped.args, ("crm.lead", "read_group"))
        self.assertEqual(grouped.kwargs["att"][0], domain)
        self.assertEqual(self.bot.search_read.call_args.kwargs["constraints"], domain)
        self.assertIn("Example deal", self.stdout.getvalue())
        self.assert_read_only()

    def test_sales_filters_order_and_currency_subtotals_cover_only_displayed_rows(self):
        self.bot.count.return_value = 200
        self.bot.custom.return_value = [
            {
                "name": f"S{index}",
                "state": "sale",
                "amount_total": amount,
                "currency_id": currency,
            }
            for index, (amount, currency) in enumerate(
                [(0.1, [1, "USD"]), (0.2, [1, "USD"]), (1, [2, "USD"])], start=1
            )
        ]
        sales = examples["sales_orders"]
        with patch.object(sales, "show_table") as table:
            self.assertEqual(
                sales.main(
                    [
                        "--since",
                        "2026-01-01",
                        "--state",
                        "sale",
                        "--mine",
                        "--limit",
                        "3",
                    ]
                ),
                0,
            )
        domain = self.bot.count.call_args.kwargs["constraints"]
        for condition in (
            ("date_order", ">=", "2026-01-01 00:00:00"),
            ("state", "=", "sale"),
            ("user_id", "=", 7),
        ):
            self.assertIn(condition, domain)
        read = self.bot.custom.call_args
        self.assertEqual(read.args, ("sale.order", "search_read"))
        self.assertEqual(read.kwargs["att"], [domain])
        self.assertEqual(read.kwargs["kwargs"]["limit"], 3)
        self.assertEqual(read.kwargs["kwargs"]["order"], "date_order desc, id desc")
        self.assertEqual(table.call_args.args[1], [["USD", "0.30"], ["USD", "1.00"]])
        self.assertIn("displayed orders only", self.stdout.getvalue())
        self.assert_read_only()

    def test_field_filter_matches_names_and_labels_case_insensitively(self):
        self.bot.get_fields.return_value = {
            "x_other": {"string": "Invisible", "type": "char"},
            "z_owner": {"string": "Assigned Customer", "type": "many2one"},
            "customer_id": {"string": "Company", "type": "many2one"},
        }
        self.assertEqual(
            examples["model_fields"].main(
                ["--model", "sale.order", "--query", "CUSTOMER", "--limit", "1"]
            ),
            0,
        )
        self.assertEqual(self.bot.get_fields.call_args.args, ("sale.order",))
        output = self.stdout.getvalue()
        self.assertIn("Matching fields: 2; displayed: 1", output)
        self.assertIn("customer_id", output)
        self.assertNotIn("z_owner", output)
        self.assertNotIn("x_other", output)
        self.assert_read_only()


if __name__ == "__main__":
    unittest.main()
