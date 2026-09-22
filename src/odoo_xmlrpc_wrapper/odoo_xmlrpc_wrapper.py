"""A synchronous, authenticated client for Odoo's XML-RPC API."""

import ipaddress
import math
import re
import ssl
import xmlrpc.client  # nosec B411: every proxy uses a defused, size-limited transport.
from urllib.parse import urlsplit

from defusedxml.xmlrpc import DefusedExpatParser, DefusedGzipDecodedResponse

_MAX_RESPONSE_BYTES = 30 * 1024 * 1024


class _SafeResponseMixin:
    """Reject XML entities and bound both ordinary and gzip response bodies."""

    def getparser(self):
        target = xmlrpc.client.Unmarshaller(
            use_datetime=self._use_datetime,
            use_builtin_types=self._use_builtin_types,
        )
        parser = DefusedExpatParser(
            target, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
        return parser, target

    def parse_response(self, response):
        stream = response
        if (
            hasattr(response, "getheader")
            and (response.getheader("Content-Encoding", "") or "").lower() == "gzip"
        ):
            stream = DefusedGzipDecodedResponse(response, limit=_MAX_RESPONSE_BYTES)
        parser, target = self.getparser()
        size = 0
        try:
            while True:
                data = stream.read(min(8192, _MAX_RESPONSE_BYTES - size + 1))
                if not data:
                    break
                size += len(data)
                if size > _MAX_RESPONSE_BYTES:
                    raise ValueError("XML-RPC response exceeds the 30 MiB size limit")
                parser.feed(data)
            parser.close()
            return target.close()
        finally:
            if stream is not response:
                stream.close()


class _TimeoutTransport(_SafeResponseMixin, xmlrpc.client.Transport):
    """HTTP transport with a connection-local socket timeout."""

    def __init__(self, timeout):
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


class _TimeoutSafeTransport(_SafeResponseMixin, xmlrpc.client.SafeTransport):
    """HTTPS transport with certificate verification and a local timeout."""

    def __init__(self, timeout):
        super().__init__(context=ssl.create_default_context())
        self.timeout = timeout

    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


def _required_string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _base_url(host, secured):
    """Validate an origin and optional path without reflecting its contents."""
    _required_string(host, "host")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in host):
        raise ValueError("host must not contain whitespace or control characters")
    if any(char in host for char in ("?", "#", "\\")):
        raise ValueError("host must not contain a query, fragment, or backslash")
    scheme = "https" if secured else "http"
    try:
        parsed = urlsplit(host if "://" in host else f"{scheme}://{host}")
        port = parsed.port
        hostname = parsed.hostname
    except ValueError:
        raise ValueError("host is not a valid HTTP(S) address") from None
    if parsed.scheme != scheme:
        raise ValueError("host scheme must match the secured setting")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("host must not contain embedded credentials")
    if not hostname or parsed.netloc.endswith(":") or port == 0:
        raise ValueError("host must contain a valid hostname and optional port")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        labels = hostname.rstrip(".").split(".")
        if len(hostname) > 253 or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9])?", label)
            for label in labels
        ):
            raise ValueError("host must contain a valid hostname") from None
    return f"{scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def _record_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("record IDs must be positive integers")
    return value


def _record_ids(ids):
    if isinstance(ids, (list, tuple)):
        return [_record_id(value) for value in ids]
    return [_record_id(ids)]


def _string_list(value, name):
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{name} must be a list or tuple of non-empty strings")
    return list(value)


def _domain(constraints):
    if constraints is None:
        return []
    if not isinstance(constraints, (list, tuple)):
        raise ValueError("constraints must be a list or tuple")
    return list(constraints)


def _pagination(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


class Bot:
    """Connect to Odoo and reuse its authenticated XML-RPC endpoints.

    HTTPS verifies server certificates. HTTP requires ``secured=False``.
    Instances own their connections and should be closed or used with ``with``.
    An instance maintains an active model and is not safe for concurrent use.
    """

    def __init__(
        self,
        host: str = None,
        db: str = None,
        userlogin: str = None,
        password: str = None,
        secured: bool = True,
        test: bool = False,
        timeout: float = 30.0,
    ) -> None:
        """Authenticate and read the user's name without writing to stdout.

        ``host`` accepts a hostname, optional port/path, or an HTTP(S) URL
        whose scheme matches ``secured``. Embedded URL credentials, query
        strings, and fragments are rejected. ``timeout`` is a positive,
        finite socket timeout in seconds, not a total-operation deadline.

        With ``test=True``, HTTPS demo credentials replace host and login
        arguments, and the returned demo endpoint must also use HTTPS.
        Responses are limited to 30 MiB and reject DTDs and XML entities.

        Raises:
            ValueError: Invalid local arguments or demo configuration.
            PermissionError: Odoo rejects the supplied credentials.
        """
        self.successful = False
        self.model = None
        self._closed = False
        self._transports = []
        if not isinstance(secured, bool) or not isinstance(test, bool):
            raise ValueError("secured and test must be booleans")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("timeout must be a finite positive number")
        try:
            self.timeout = float(timeout)
        except (OverflowError, ValueError):
            raise ValueError("timeout must be a finite positive number") from None
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout must be a finite positive number")

        try:
            if test:
                demo = self._proxy("https://demo.odoo.com/start")
                try:
                    info = demo.start()
                finally:
                    self._transports[-1].close()
                if not isinstance(info, dict) or not all(
                    key in info for key in ("host", "database", "user", "password")
                ):
                    raise ValueError("Odoo returned invalid demo configuration")
                host, db, userlogin, password = (
                    info["host"],
                    info["database"],
                    info["user"],
                    info["password"],
                )
                secured = True
                if not isinstance(host, str) or not host.startswith("https://"):
                    raise ValueError("Odoo demo host must be an HTTPS URL")

            base_url = _base_url(host, secured)
            self.HOST = base_url.split("://", 1)[1]
            self.URL = f"{base_url}/xmlrpc/2"
            self.DB = _required_string(db, "db")
            self.USERLOGIN = _required_string(userlogin, "userlogin")
            self.__PASSWORD = _required_string(password, "password")
            self.__common = self._proxy(f"{self.URL}/common")
            self.version = self.__common.version()
            self.uid = self.__common.authenticate(
                self.DB, self.USERLOGIN, self.__PASSWORD, {}
            )
            if (
                isinstance(self.uid, bool)
                or not isinstance(self.uid, int)
                or self.uid <= 0
            ):
                raise PermissionError("Odoo authentication failed")
            self.__orm = self._proxy(f"{self.URL}/object")
            profiles = self.read("res.users", ids=self.uid, fields=["name"])
            if (
                not isinstance(profiles, list)
                or not profiles
                or not isinstance(profiles[0], dict)
                or not isinstance(profiles[0].get("name"), str)
            ):
                raise ValueError("Odoo returned an invalid user profile")
            self.profile = profiles[0]
            self.name = self.profile["name"]
            self.successful = True
        except BaseException:
            self.close()
            raise

    def _proxy(self, url):
        transport_type = (
            _TimeoutSafeTransport if url.startswith("https://") else _TimeoutTransport
        )
        transport = transport_type(self.timeout)
        self._transports.append(transport)
        return xmlrpc.client.ServerProxy(url, transport=transport)

    def _model(self, model):
        if self._closed:
            raise RuntimeError("Bot is closed")
        selected = self.model if model is None else model
        if not isinstance(selected, str) or not all(
            part.isidentifier() for part in selected.split(".")
        ):
            raise ValueError("model must be a non-empty dotted model name")
        self.model = selected
        return selected

    def close(self) -> None:
        """Close all owned transports; repeated calls are harmless."""
        self._closed = True
        self.successful = False
        for transport in self._transports:
            transport.close()
        self._transports.clear()

    def __enter__(self):
        if self._closed:
            raise RuntimeError("Bot is closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def status(self) -> str:
        """Return connection details without including the password."""
        if self._closed:
            return "Connection closed"
        return (
            f"Successfully Logged\nName: {self.name}\nDB: {self.DB}\n"
            f"HOST: {self.HOST}\nVERSION: {self.version['server_version']}"
        )

    def search_read(
        self,
        model: str = None,
        constraints: list = None,
        fields: list = None,
        limit: int = None,
    ) -> list:
        """Search a domain and read fields (default: ``[\"name\"]``).

        Explicit empty fields and ``limit=0`` are passed through to Odoo.
        Omitting a model reuses the previous model, initially ``res.users``.
        """
        kwargs = {
            "fields": ["name"] if fields is None else _string_list(fields, "fields")
        }
        if limit is not None:
            kwargs["limit"] = _pagination(limit, "limit")
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            "search_read",
            [_domain(constraints)],
            kwargs,
        )

    def search(
        self,
        model: str = None,
        constraints: list = None,
        offset: int = None,
        limit: int = None,
    ) -> list:
        """Return matching IDs, preserving explicit zero limit and offset."""
        kwargs = {}
        if offset is not None:
            kwargs["offset"] = _pagination(offset, "offset")
        if limit is not None:
            kwargs["limit"] = _pagination(limit, "limit")
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            "search",
            [_domain(constraints)],
            kwargs,
        )

    def count(self, model: str = None, constraints: list = None) -> int:
        """Count matching records on the server without downloading their IDs."""
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            "search_count",
            [_domain(constraints)],
        )

    def read(self, model: str = None, ids: list = None, fields: list = None) -> list:
        """Read a positive record ID or list/tuple of IDs, optionally by field."""
        record_ids = _record_ids(ids)
        kwargs = {} if fields is None else {"fields": _string_list(fields, "fields")}
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            "read",
            [record_ids],
            kwargs,
        )

    def delete(self, model: str = None, ids: list = None) -> bool:
        """Delete a positive ID or list/tuple of IDs and return Odoo's result."""
        record_ids = _record_ids(ids)
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            "unlink",
            [record_ids],
        )

    def create(self, model: str = None, the_obj: dict = None) -> int:
        """Create a record from a dictionary and return its ID."""
        if not isinstance(the_obj, dict):
            raise ValueError("the_obj must be a dictionary")
        return self.__orm.execute_kw(
            self.DB, self.uid, self.__PASSWORD, self._model(model), "create", [the_obj]
        )

    def update(
        self, model: str = None, the_id: int = None, the_obj: dict = None
    ) -> bool:
        """Update one positive record ID and return Odoo's result."""
        record_id = _record_id(the_id)
        if not isinstance(the_obj, dict):
            raise ValueError("the_obj must be a dictionary")
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            "write",
            [[record_id], the_obj],
        )

    def get_fields(self, model: str = None, attributes: list = None) -> dict:
        """Read field metadata, preserving explicitly empty attributes."""
        kwargs = (
            {}
            if attributes is None
            else {"attributes": _string_list(attributes, "attributes")}
        )
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            "fields_get",
            [],
            kwargs,
        )

    def custom(
        self,
        model: str = None,
        command: str = None,
        att: list = None,
        kwargs: dict = None,
    ):
        """Call a public Odoo method with positional and optional keyword args.

        Omitting ``att`` preserves the historical ``[[]]`` default; passing
        ``att=[]`` sends no positional arguments. Defaults are never shared.
        """
        if (
            not isinstance(command, str)
            or not command.isidentifier()
            or command.startswith("_")
        ):
            raise ValueError("command must be a public method name")
        if att is not None and not isinstance(att, (list, tuple)):
            raise ValueError("att must be a list or tuple of positional arguments")
        if kwargs is not None and (
            not isinstance(kwargs, dict)
            or any(not isinstance(key, str) for key in kwargs)
        ):
            raise ValueError("kwargs must be a dictionary with string keys")
        args = (
            self.DB,
            self.uid,
            self.__PASSWORD,
            self._model(model),
            command,
            [[]] if att is None else list(att),
        )
        if kwargs is None:
            return self.__orm.execute_kw(*args)
        return self.__orm.execute_kw(*args, kwargs)
