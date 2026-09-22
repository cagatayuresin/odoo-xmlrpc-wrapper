"""Offline behavioral and security regression tests; no Odoo server is required."""

import contextlib
import gzip
import io
import ssl
import unittest
import xmlrpc.client
from unittest.mock import MagicMock, Mock, patch

from defusedxml.common import DefusedXmlException

from odoo_xmlrpc_wrapper import odoo_xmlrpc_wrapper as oxw


class BotTestCase(unittest.TestCase):
    def setUp(self):
        self.common = MagicMock()
        self.common.version.return_value = {"server_version": "18.0"}
        self.common.authenticate.return_value = 7
        self.orm = MagicMock()
        self.orm.execute_kw.return_value = [{"id": 7, "name": "Test User"}]
        self.demo = MagicMock()
        self.demo.start.return_value = {
            "host": "https://demo.example.test",
            "database": "demo-db",
            "user": "demo-user",
            "password": "demo-secret",
        }
        self.transports = []
        patcher = patch.object(xmlrpc.client, "ServerProxy", side_effect=self._proxy)
        self.proxy = patcher.start()
        self.addCleanup(patcher.stop)

    def _proxy(self, url, **kwargs):
        transport = kwargs["transport"]
        if transport not in self.transports:
            transport.close = Mock(wraps=transport.close)
            self.transports.append(transport)
        if url.endswith("/common"):
            return self.common
        if url.endswith("/object"):
            return self.orm
        if url == "https://demo.odoo.com/start":
            return self.demo
        self.fail(f"Unexpected XML-RPC endpoint: {url}")

    def make_bot(self, **overrides):
        options = {
            "host": "odoo.example.test",
            "db": "test-db",
            "userlogin": "test-user",
            "password": "private-test-secret",
        }
        options.update(overrides)
        bot = oxw.Bot(**options)
        self.addCleanup(bot.close)
        return bot

    def ready_bot(self, **overrides):
        bot = self.make_bot(**overrides)
        self.orm.execute_kw.reset_mock()
        return bot

    def assert_rpc(self, model, method, args, kwargs=None):
        self.orm.execute_kw.assert_called_once()
        call = self.orm.execute_kw.call_args
        expected = (
            "test-db",
            7,
            "private-test-secret",
            model,
            method,
            args,
        )
        if kwargs is not None:
            expected += (kwargs,)
        self.assertEqual(call.args, expected)
        self.assertEqual(call.kwargs, {})


class AuthenticationTests(BotTestCase):
    def test_login_fetches_profile_without_printing(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            bot = self.make_bot()
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.common.authenticate.assert_called_once_with(
            "test-db", "test-user", "private-test-secret", {}
        )
        self.assert_rpc("res.users", "read", [[7]], {"fields": ["name"]})
        self.assertTrue(bot.successful)
        self.assertEqual(bot.uid, 7)
        self.assertEqual(bot.name, "Test User")
        self.assertEqual(bot.profile, {"id": 7, "name": "Test User"})
        self.assertEqual(bot.model, "res.users")

    def test_authentication_failure_does_not_disclose_credentials(self):
        self.common.authenticate.return_value = False
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(PermissionError) as error:
                self.make_bot()
        output = str(error.exception) + stdout.getvalue() + stderr.getvalue()
        for secret in ("private-test-secret", "test-user", "test-db"):
            self.assertNotIn(secret, output)
        self.orm.execute_kw.assert_not_called()
        for transport in self.transports:
            transport.close.assert_called_once()

    def test_status_is_explicit_and_does_not_include_password(self):
        bot = self.make_bot()
        status = bot.status()
        for value in ("Test User", "test-db", "odoo.example.test", "18.0"):
            self.assertIn(value, status)
        self.assertNotIn("private-test-secret", status)

    def test_missing_or_invalid_credentials_fail_before_network(self):
        for field in ("db", "userlogin", "password"):
            for value in (None, "", "   ", 42, True):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        self.make_bot(**{field: value})
        self.proxy.assert_not_called()

    def test_password_with_spaces_is_preserved(self):
        self.make_bot(password="  significant spaces  ")
        self.common.authenticate.assert_called_once_with(
            "test-db", "test-user", "  significant spaces  ", {}
        )

    def test_initialization_failure_closes_opened_transports(self):
        failure = xmlrpc.client.Fault(1, "server unavailable")
        self.common.version.side_effect = failure
        with self.assertRaises(xmlrpc.client.Fault) as error:
            self.make_bot()
        self.assertIs(error.exception, failure)
        self.assertTrue(self.transports)
        for transport in self.transports:
            transport.close.assert_called_once()

    def test_profile_failure_closes_opened_transports(self):
        self.orm.execute_kw.side_effect = xmlrpc.client.Fault(2, "profile denied")
        with self.assertRaises(xmlrpc.client.Fault):
            self.make_bot()
        for transport in self.transports:
            transport.close.assert_called_once()


class TransportSecurityTests(BotTestCase):
    def test_https_is_default_and_certificate_verification_is_enabled(self):
        self.make_bot()
        self.assertEqual(
            [call.args[0] for call in self.proxy.call_args_list],
            [
                "https://odoo.example.test/xmlrpc/2/common",
                "https://odoo.example.test/xmlrpc/2/object",
            ],
        )
        for transport in self.transports:
            self.assertIsInstance(transport, xmlrpc.client.SafeTransport)
            connection = transport.make_connection("odoo.example.test")
            self.assertEqual(connection.timeout, 30.0)
            self.assertTrue(connection._context.check_hostname)
            self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)

    def test_custom_timeout_reaches_https_connection(self):
        self.make_bot(timeout=2.5)
        for transport in self.transports:
            self.assertEqual(
                transport.make_connection("odoo.example.test").timeout, 2.5
            )

    def test_http_requires_explicit_opt_in_and_keeps_timeout(self):
        self.make_bot(host="http://localhost:8069", secured=False, timeout=4)
        for call in self.proxy.call_args_list:
            self.assertTrue(call.args[0].startswith("http://localhost:8069/"))
        for transport in self.transports:
            self.assertNotIsInstance(transport, xmlrpc.client.SafeTransport)
            self.assertEqual(transport.make_connection("localhost:8069").timeout, 4)

    def test_full_https_url_preserves_reverse_proxy_prefix(self):
        self.make_bot(host="https://odoo.example.test:8443/erp/")
        self.assertEqual(
            [call.args[0] for call in self.proxy.call_args_list],
            [
                "https://odoo.example.test:8443/erp/xmlrpc/2/common",
                "https://odoo.example.test:8443/erp/xmlrpc/2/object",
            ],
        )

    def test_unsafe_or_malformed_hosts_fail_before_network(self):
        invalid_hosts = (
            None,
            "",
            "   ",
            "odoo.example.test\n",
            "https://user:password@odoo.example.test",
            "https://odoo.example.test?password=secret",
            "https://odoo.example.test#fragment",
            "ftp://odoo.example.test",
            "http://odoo.example.test",
            "https://odoo.example.test:invalid",
            "https://odoo.example.test:70000",
        )
        for host in invalid_hosts:
            with self.subTest(host=host):
                with self.assertRaises((TypeError, ValueError)):
                    self.make_bot(host=host)
        self.proxy.assert_not_called()

    def test_https_url_cannot_silently_be_downgraded_to_http(self):
        with self.assertRaises(ValueError):
            self.make_bot(host="https://odoo.example.test", secured=False)
        self.proxy.assert_not_called()

    def test_timeout_must_be_positive_and_finite(self):
        for timeout in (None, False, True, 0, -1, "5", float("nan"), float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises((TypeError, ValueError)):
                    self.make_bot(timeout=timeout)
        self.proxy.assert_not_called()

    def test_security_and_demo_flags_require_explicit_booleans(self):
        for flag in ("secured", "test"):
            for value in (None, 0, 1, "", "False"):
                with self.subTest(flag=flag, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        self.make_bot(**{flag: value})
        self.proxy.assert_not_called()

    def test_demo_credentials_use_https_even_when_secured_is_false(self):
        bot = self.make_bot(test=True, secured=False, timeout=8)
        self.assertEqual(bot.URL, "https://demo.example.test/xmlrpc/2")
        self.common.authenticate.assert_called_once_with(
            "demo-db", "demo-user", "demo-secret", {}
        )
        for call in self.proxy.call_args_list:
            self.assertTrue(call.args[0].startswith("https://"))
        for transport in self.transports:
            self.assertEqual(transport.make_connection("demo.example.test").timeout, 8)

    def test_demo_response_cannot_redirect_credentials_to_unsafe_url(self):
        for host in (
            "http://demo.example.test",
            "https://user:secret@demo.example.test",
            "https://demo.example.test?token=secret",
            "https://demo.example.test#fragment",
        ):
            with self.subTest(host=host):
                self.demo.start.return_value["host"] = host
                self.proxy.reset_mock()
                with self.assertRaises(ValueError):
                    self.make_bot(test=True)
                self.assertEqual(
                    [call.args[0] for call in self.proxy.call_args_list],
                    ["https://demo.odoo.com/start"],
                )
        self.common.authenticate.assert_not_called()


class XmlResponseSecurityTests(BotTestCase):
    @staticmethod
    def response(payload, compressed=False):
        response = io.BytesIO(gzip.compress(payload) if compressed else payload)
        response.getheader = Mock(
            side_effect=lambda name, default=None: (
                "gzip" if compressed and name.lower() == "content-encoding" else default
            )
        )
        return response

    def test_valid_response_is_decoded_over_both_transports(self):
        self.make_bot()
        self.make_bot(secured=False)
        expected = ([{"id": 42, "name": "Ada"}],)
        payload = xmlrpc.client.dumps(expected, methodresponse=True).encode()
        for transport in self.transports:
            with self.subTest(transport=type(transport).__name__):
                self.assertEqual(
                    transport.parse_response(self.response(payload)), expected
                )

    def test_valid_compressed_response_is_decoded(self):
        self.make_bot()
        payload = xmlrpc.client.dumps((42,), methodresponse=True).encode()
        self.assertEqual(
            self.transports[0].parse_response(self.response(payload, compressed=True)),
            (42,),
        )

    def test_server_fault_response_is_preserved(self):
        self.make_bot()
        fault = xmlrpc.client.Fault(2, "Access denied")
        payload = xmlrpc.client.dumps(fault).encode()
        with self.assertRaises(xmlrpc.client.Fault) as error:
            self.transports[0].parse_response(self.response(payload))
        self.assertEqual(error.exception.faultCode, 2)
        self.assertEqual(error.exception.faultString, "Access denied")

    def test_dtd_entity_expansion_and_external_entities_are_rejected(self):
        self.make_bot()
        self.make_bot(secured=False)
        documents = (
            ("<!DOCTYPE methodResponse>", "safe"),
            (
                '<!DOCTYPE methodResponse [<!ENTITY secret "expanded">]>',
                "&secret;",
            ),
            (
                '<!DOCTYPE methodResponse [<!ENTITY secret SYSTEM "file:///etc/passwd">]>',
                "&secret;",
            ),
            (
                '<!DOCTYPE methodResponse SYSTEM "https://attacker.invalid/external.dtd">',
                "safe",
            ),
        )
        for transport in self.transports:
            for doctype, content in documents:
                with self.subTest(transport=type(transport).__name__, doctype=doctype):
                    payload = (
                        '<?xml version="1.0"?>'
                        f"{doctype}<methodResponse><params><param><value>"
                        f"<string>{content}</string>"
                        "</value></param></params></methodResponse>"
                    ).encode()
                    with self.assertRaises(DefusedXmlException):
                        transport.parse_response(self.response(payload))

    def test_stdlib_xmlrpc_parser_is_not_globally_replaced(self):
        self.make_bot()
        self.assertEqual(xmlrpc.client.ExpatParser.__module__, "xmlrpc.client")

    def test_oversized_xml_response_is_rejected(self):
        self.make_bot()
        payload = xmlrpc.client.dumps(("x" * 512,), methodresponse=True).encode()
        with patch.object(oxw, "_MAX_RESPONSE_BYTES", 256):
            with self.assertRaises(ValueError):
                self.transports[0].parse_response(self.response(payload))

    def test_compressed_xml_cannot_bypass_response_size_limit(self):
        self.make_bot()
        payload = xmlrpc.client.dumps(("x" * 8192,), methodresponse=True).encode()
        self.assertLess(len(gzip.compress(payload)), 256)
        with patch.object(oxw, "_MAX_RESPONSE_BYTES", 256):
            with self.assertRaises(ValueError):
                self.transports[0].parse_response(
                    self.response(payload, compressed=True)
                )


class RecordOperationTests(BotTestCase):
    def test_search_read_uses_domain_fields_and_limit(self):
        bot = self.ready_bot()
        domain = [("active", "=", True)]
        records = [{"id": 42, "name": "Ada"}]
        self.orm.execute_kw.return_value = records
        self.assertEqual(
            bot.search_read("res.partner", domain, ["name"], limit=10), records
        )
        self.assert_rpc(
            "res.partner", "search_read", [domain], {"fields": ["name"], "limit": 10}
        )
        self.assertEqual(domain, [("active", "=", True)])

    def test_search_read_defaults_to_name_and_empty_domain(self):
        bot = self.ready_bot()
        bot.search_read()
        self.assert_rpc("res.users", "search_read", [[]], {"fields": ["name"]})

    def test_search_read_preserves_empty_fields_and_zero_limit(self):
        bot = self.ready_bot()
        bot.search_read(fields=[], limit=0)
        self.assert_rpc("res.users", "search_read", [[]], {"fields": [], "limit": 0})

    def test_search_returns_ids_and_reuses_last_model(self):
        bot = self.ready_bot()
        self.orm.execute_kw.return_value = [42, 43]
        self.assertEqual(bot.search("res.partner"), [42, 43])
        self.orm.execute_kw.reset_mock()
        self.assertEqual(bot.search(), [42, 43])
        self.assert_rpc("res.partner", "search", [[]], {})

    def test_search_preserves_zero_offset_and_limit(self):
        bot = self.ready_bot()
        bot.search(offset=0, limit=0)
        self.assert_rpc("res.users", "search", [[]], {"offset": 0, "limit": 0})

    def test_search_pagination_combinations(self):
        bot = self.ready_bot()
        for kwargs in ({"offset": 4}, {"limit": 5}, {"offset": 4, "limit": 5}):
            with self.subTest(kwargs=kwargs):
                self.orm.execute_kw.reset_mock()
                bot.search("res.partner", **kwargs)
                self.assert_rpc("res.partner", "search", [[]], kwargs)

    def test_count_uses_server_search_count(self):
        bot = self.ready_bot()
        self.orm.execute_kw.return_value = 1000000
        domain = [("active", "=", True)]
        self.assertEqual(bot.count("res.partner", domain), 1000000)
        self.assert_rpc("res.partner", "search_count", [domain])

    def test_read_accepts_scalar_list_and_tuple_ids(self):
        bot = self.ready_bot()
        for ids in (42, [42], (42,)):
            with self.subTest(ids=ids):
                self.orm.execute_kw.reset_mock()
                bot.read("res.partner", ids=ids, fields=["name"])
                self.assert_rpc("res.partner", "read", [[42]], {"fields": ["name"]})

    def test_read_distinguishes_omitted_and_empty_fields(self):
        bot = self.ready_bot()
        bot.read(ids=[])
        self.assert_rpc("res.users", "read", [[]], {})
        self.orm.execute_kw.reset_mock()
        bot.read(ids=[], fields=[])
        self.assert_rpc("res.users", "read", [[]], {"fields": []})

    def test_create_returns_new_id(self):
        bot = self.ready_bot()
        values = {"name": "Ada"}
        self.orm.execute_kw.return_value = 42
        self.assertEqual(bot.create("res.partner", values), 42)
        self.assert_rpc("res.partner", "create", [values])

    def test_update_returns_server_result(self):
        bot = self.ready_bot()
        for result in (True, False):
            with self.subTest(result=result):
                self.orm.execute_kw.reset_mock()
                self.orm.execute_kw.return_value = result
                self.assertIs(bot.update("res.partner", 42, {"name": "Grace"}), result)
                self.assert_rpc("res.partner", "write", [[42], {"name": "Grace"}])

    def test_update_requires_record_id_before_rpc(self):
        bot = self.ready_bot()
        with self.assertRaises((TypeError, ValueError)):
            bot.update("res.partner", the_obj={"name": "Grace"})
        self.orm.execute_kw.assert_not_called()

    def test_delete_normalizes_ids_and_returns_server_result(self):
        bot = self.ready_bot()
        for ids, normalized in (
            (42, [42]),
            ([42, 43], [42, 43]),
            ((42,), [42]),
            ([], []),
        ):
            with self.subTest(ids=ids):
                self.orm.execute_kw.reset_mock()
                self.orm.execute_kw.return_value = True
                self.assertIs(bot.delete("res.partner", ids), True)
                self.assert_rpc("res.partner", "unlink", [normalized])

    def test_get_fields_preserves_requested_attributes(self):
        bot = self.ready_bot()
        fields = {"name": {"type": "char"}}
        self.orm.execute_kw.return_value = fields
        self.assertEqual(bot.get_fields("res.partner", ["type"]), fields)
        self.assert_rpc("res.partner", "fields_get", [], {"attributes": ["type"]})

    def test_get_fields_distinguishes_omitted_and_empty_attributes(self):
        bot = self.ready_bot()
        bot.get_fields()
        self.assert_rpc("res.users", "fields_get", [], {})
        self.orm.execute_kw.reset_mock()
        bot.get_fields(attributes=[])
        self.assert_rpc("res.users", "fields_get", [], {"attributes": []})

    def test_server_fault_is_preserved(self):
        bot = self.ready_bot()
        failure = xmlrpc.client.Fault(2, "Access denied")
        self.orm.execute_kw.side_effect = failure
        with self.assertRaises(xmlrpc.client.Fault) as error:
            bot.search()
        self.assertIs(error.exception, failure)


class CustomOperationTests(BotTestCase):
    def test_custom_forwards_positional_and_keyword_arguments(self):
        bot = self.ready_bot()
        kwargs = {"context": {"lang": "tr_TR"}}
        self.orm.execute_kw.return_value = "done"
        self.assertEqual(
            bot.custom("res.partner", "action_confirm", [[42]], kwargs), "done"
        )
        self.assert_rpc("res.partner", "action_confirm", [[42]], kwargs)
        self.assertEqual(kwargs, {"context": {"lang": "tr_TR"}})

    def test_custom_preserves_explicit_empty_arguments(self):
        bot = self.ready_bot()
        bot.custom(command="my_method", att=[], kwargs={})
        self.assert_rpc("res.users", "my_method", [], {})

    def test_custom_default_arguments_are_not_shared_between_calls(self):
        bot = self.ready_bot()

        def mutate_arguments(*args):
            args[5][0].append(42)

        self.orm.execute_kw.side_effect = mutate_arguments
        bot.custom(command="my_method")
        first = self.orm.execute_kw.call_args.args[5]
        bot.custom(command="my_method")
        second = self.orm.execute_kw.call_args.args[5]
        self.assertEqual(first, [[42]])
        self.assertEqual(second, [[42]])
        self.assertIsNot(first, second)
        self.assertIsNot(first[0], second[0])

    def test_custom_rejects_invalid_or_private_methods_before_rpc(self):
        bot = self.ready_bot()
        for command in (
            None,
            "",
            "   ",
            "_private",
            "search.read",
            "action confirm",
            42,
        ):
            with self.subTest(command=command):
                with self.assertRaises((TypeError, ValueError)):
                    bot.custom(command=command)
        self.orm.execute_kw.assert_not_called()


class InputValidationTests(BotTestCase):
    def test_invalid_models_fail_before_rpc(self):
        bot = self.ready_bot()
        for model in ("", "   ", 42, True):
            with self.subTest(model=model):
                with self.assertRaises((TypeError, ValueError)):
                    bot.search(model=model)
        self.orm.execute_kw.assert_not_called()

    def test_invalid_record_ids_fail_before_rpc(self):
        bot = self.ready_bot()
        invalid_ids = (
            None,
            False,
            True,
            0,
            -1,
            "42",
            [False],
            [0],
            [1, -2],
            ["42"],
            {1},
        )
        for operation in (bot.read, bot.delete):
            for ids in invalid_ids:
                with self.subTest(operation=operation.__name__, ids=ids):
                    with self.assertRaises((TypeError, ValueError)):
                        operation(ids=ids)
        self.orm.execute_kw.assert_not_called()

    def test_update_rejects_invalid_record_id(self):
        bot = self.ready_bot()
        for record_id in (False, True, 0, -1, "42", [42], (42,)):
            with self.subTest(record_id=record_id):
                with self.assertRaises((TypeError, ValueError)):
                    bot.update(the_id=record_id, the_obj={"name": "Ada"})
        self.orm.execute_kw.assert_not_called()

    def test_create_and_update_require_dictionaries(self):
        bot = self.ready_bot()
        for value in (None, [], "name", 42):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    bot.create(the_obj=value)
                with self.assertRaises((TypeError, ValueError)):
                    bot.update(the_id=42, the_obj=value)
        self.orm.execute_kw.assert_not_called()

    def test_invalid_pagination_fails_before_rpc(self):
        bot = self.ready_bot()
        for value in (-1, False, True, 1.5, "10"):
            for parameter in ("offset", "limit"):
                with self.subTest(parameter=parameter, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        bot.search(**{parameter: value})
            with self.subTest(operation="search_read", limit=value):
                with self.assertRaises((TypeError, ValueError)):
                    bot.search_read(limit=value)
        self.orm.execute_kw.assert_not_called()

    def test_invalid_domains_fail_before_rpc(self):
        bot = self.ready_bot()
        for operation in (bot.search, bot.search_read, bot.count):
            for domain in ("name = Ada", {"name": "Ada"}, 42):
                with self.subTest(operation=operation.__name__, domain=domain):
                    with self.assertRaises((TypeError, ValueError)):
                        operation(constraints=domain)
        self.orm.execute_kw.assert_not_called()

    def test_fields_and_attributes_must_be_string_sequences(self):
        bot = self.ready_bot()
        for value in ("name", [42], [None], {"name": True}):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    bot.read(ids=[42], fields=value)
                with self.assertRaises((TypeError, ValueError)):
                    bot.search_read(fields=value)
                with self.assertRaises((TypeError, ValueError)):
                    bot.get_fields(attributes=value)
        self.orm.execute_kw.assert_not_called()

    def test_custom_rejects_invalid_argument_containers(self):
        bot = self.ready_bot()
        for arguments in ("abc", 42, {"id": 42}):
            with self.subTest(att=arguments):
                with self.assertRaises((TypeError, ValueError)):
                    bot.custom(command="my_method", att=arguments)
        for kwargs in ([], "abc", 42):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises((TypeError, ValueError)):
                    bot.custom(command="my_method", kwargs=kwargs)
        self.orm.execute_kw.assert_not_called()


class LifecycleTests(BotTestCase):
    def test_close_releases_connections_once_without_remote_close_rpc(self):
        bot = self.ready_bot()
        bot.close()
        bot.close()
        for transport in self.transports:
            transport.close.assert_called_once()
        self.common.close.assert_not_called()
        self.orm.close.assert_not_called()
        self.orm.execute_kw.assert_not_called()

    def test_context_manager_closes_connections(self):
        bot = self.ready_bot()
        with bot as active:
            self.assertIs(active, bot)
        for transport in self.transports:
            transport.close.assert_called_once()

    def test_context_manager_preserves_exceptions_and_closes_connections(self):
        bot = self.ready_bot()
        failure = RuntimeError("application failure")
        with self.assertRaises(RuntimeError) as error:
            with bot:
                raise failure
        self.assertIs(error.exception, failure)
        for transport in self.transports:
            transport.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
