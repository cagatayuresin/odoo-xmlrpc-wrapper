"""A small wrapper for the Odoo XML-RPC API."""

from importlib.metadata import PackageNotFoundError, version

from .odoo_xmlrpc_wrapper import Bot

try:
    __version__ = version("odoo_xmlrpc_wrapper")
except PackageNotFoundError:  # Source trees without an installed distribution.
    __version__ = "0+unknown"

__author__ = "Cagatay URESIN"
__all__ = ["Bot", "__version__"]
