"""Complete BBMB's missing intermediate without weakening TLS verification."""

import ssl
from importlib.resources import files

import requests
from requests.adapters import HTTPAdapter


def ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=requests.certs.where())
    intermediate = files("river_watch").joinpath("certificates/godaddy-g2-intermediate.pem")
    context.load_verify_locations(cadata=intermediate.read_text(encoding="ascii"))
    context.verify_flags |= ssl.VERIFY_X509_STRICT
    # Python 3.13 permits a trusted intermediate to terminate the chain by
    # default. Require this intermediate to chain to the normal public roots.
    context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    return context


class BBMBAdapter(HTTPAdapter):
    def __init__(self):
        self._ssl_context = ssl_context()
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        host, pool = super().build_connection_pool_key_attributes(request, verify, cert)
        pool["ssl_context"] = self._ssl_context
        return host, pool


def session() -> requests.Session:
    sess = requests.Session()
    # Include the trailing slash so Requests cannot match a different hostname
    # such as bbmb.gov.in.example.org. Redirects use the destination's adapter.
    sess.mount("https://bbmb.gov.in/", BBMBAdapter())
    return sess
