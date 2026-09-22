"""Offline checks for the interactive live runner; never connect to Odoo."""

import contextlib
import importlib.util
import io
import unittest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from xmlrpc.client import Fault

from odoo_xmlrpc_wrapper import Bot

_SCRIPT = Path(__file__).resolve().parents[1] / "examples" / "live_smoke_test.py"
_SPEC = importlib.util.spec_from_file_location("live_smoke_test", _SCRIPT)
smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(smoke)


class LiveSmokeTestTests(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.stdout = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.stdin = stack.enter_context(patch.object(smoke.sys, "stdin"))
        self.stdin.isatty.return_value = True
        self.input = stack.enter_context(
            patch("builtins.input", side_effect=["odoo.example.test", "db", "login"])
        )
        self.secret = "private-live-test-secret"
        self.getpass = stack.enter_context(
            patch.object(smoke.getpass, "getpass", return_value=self.secret)
        )
        self.bot = MagicMock(spec=Bot)
        self.bot.uid = 7
        self.bot.version = {"server_version": "18.0"}
        self.bot.__enter__.return_value = self.bot
        self.bot.__exit__.return_value = False
        self.bot.read.return_value = [{"id": 7, "name": "Private Name"}]
        self.bot.search.return_value = [7]
        self.bot.search_read.return_value = [{"id": 7, "name": "Private Name"}]
        self.bot.count.return_value = 1
        self.bot.get_fields.return_value = {"name": {"type": "char"}}
        self.bot.custom.return_value = 1
        self.factory = stack.enter_context(
            patch.object(smoke, "Bot", return_value=self.bot)
        )

    def test_success_only_reads_current_user_without_exposing_password(self):
        self.assertEqual(smoke.main([]), 0)
        self.factory.assert_called_once_with(
            host="odoo.example.test",
            db="db",
            userlogin="login",
            password=self.secret,
            secured=True,
            timeout=30,
        )
        domain = [("id", "=", 7)]
        self.assertEqual(
            self.bot.method_calls,
            [
                call.read("res.users", ids=[7], fields=["name"]),
                call.search("res.users", constraints=domain, offset=0, limit=1),
                call.search_read(
                    "res.users", constraints=domain, fields=["name"], limit=1
                ),
                call.count("res.users", constraints=domain),
                call.get_fields("res.users", attributes=["type"]),
                call.custom("res.users", "search_count", att=[domain], kwargs={}),
            ],
        )
        for operation in (self.bot.create, self.bot.update, self.bot.delete):
            operation.assert_not_called()
        self.bot.__exit__.assert_called_once_with(None, None, None)
        self.assertEqual(self.input.call_count, 3)
        for prompt in self.input.call_args_list:
            self.assertNotIn("password", prompt.args[0].lower())
        self.getpass.assert_called_once_with("Password / API key (hidden): ")
        output = self.stdout.getvalue() + self.stderr.getvalue()
        self.assertNotIn(self.secret, output)
        self.assertNotIn("Private Name", output)
        self.assertIn("SUCCESS: all live read checks passed.", output)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_rpc_fault_does_not_expose_server_details_or_password(self):
        self.bot.search.side_effect = Fault(
            1, f"Server traceback containing {self.secret} and private-data-marker"
        )
        self.assertEqual(smoke.main([]), 1)
        output = self.stdout.getvalue() + self.stderr.getvalue()
        self.assertIn("XML-RPC fault", self.stderr.getvalue())
        for value in (self.secret, "private-data-marker", "Server traceback"):
            self.assertNotIn(value, output)
        self.assertNotIn("SUCCESS", output)
        self.bot.__exit__.assert_called_once()

    def test_unexpected_count_fails_without_reporting_success(self):
        self.bot.count.return_value = 2
        self.assertEqual(smoke.main([]), 1)
        self.assertIn("ValueError", self.stderr.getvalue())
        self.assertNotIn("SUCCESS", self.stdout.getvalue())
        self.bot.get_fields.assert_not_called()
        self.bot.custom.assert_not_called()
        self.bot.__exit__.assert_called_once()

    def test_noninteractive_stdin_rejects_before_reading_credentials_or_connecting(
        self,
    ):
        self.stdin.isatty.return_value = False
        with self.assertRaises(SystemExit) as error:
            smoke.main([])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("interactive terminal", self.stderr.getvalue())
        self.input.assert_not_called()
        self.getpass.assert_not_called()
        self.factory.assert_not_called()

    def test_getpass_fallback_warning_prevents_connection(self):
        def warn_instead_of_hiding_password(prompt):
            warnings.warn(
                "Cannot hide input", smoke.getpass.GetPassWarning, stacklevel=2
            )
            self.fail("Password fallback must stop before reading an echoed secret")

        self.getpass.side_effect = warn_instead_of_hiding_password
        self.assertEqual(smoke.main([]), 1)
        self.assertIn("cannot hide password input", self.stderr.getvalue())
        self.factory.assert_not_called()
        self.assertNotIn(self.secret, self.stdout.getvalue() + self.stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
