"""Refuses to run the destructive test suite against a non-local database.

conftest.py TRUNCATEs every table before and after each test, so pointing
DATABASE_URL at a hosted/production database (for example by sourcing
.env.production in the same shell) would wipe it. The check is fail-closed:
a host must be on the explicit local allow-list, every host the driver could
end up using is checked, and there is deliberately no override.
"""

from __future__ import annotations

import os
from urllib.parse import parse_qs, urlsplit

LOCAL_TEST_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "db"})


class UnsafeTestDatabase(Exception):
    """The configured database is not an obviously local test database."""


def _hosts_in(value: str) -> list[str]:
    return [h.strip().lower() for h in value.split(",") if h.strip()]


def _is_local(host: str) -> bool:
    # A unix-socket directory (host=/var/run/postgresql) is local by nature.
    return host in LOCAL_TEST_DB_HOSTS or host.startswith("/")


def assert_local_test_database(database_url: str) -> None:
    """Raises UnsafeTestDatabase unless every host the connection could use is
    local. Considers the URL's host, a ?host= override (asyncpg lets it win
    over the URL host), comma-separated multi-host lists, and PGHOST when the
    URL names no host at all. Messages name hosts only - never the password."""
    parts = urlsplit(database_url)
    hosts: list[str] = []

    netloc_host = parts.netloc.rpartition("@")[2]  # everything after the credentials
    if netloc_host.startswith("["):  # [::1]:5432
        hosts.append(netloc_host[1 : netloc_host.index("]")].lower())
    elif netloc_host:
        hosts.extend(_hosts_in(netloc_host.rsplit(":", 1)[0] if netloc_host.count(":") == 1 else netloc_host))

    for override in parse_qs(parts.query).get("host", []):
        hosts.extend(_hosts_in(override))

    if not hosts:  # nothing in the URL: the driver falls back to $PGHOST
        hosts.extend(_hosts_in(os.environ.get("PGHOST", "")))

    remote = sorted({h for h in hosts if not _is_local(h)})
    if remote:
        raise UnsafeTestDatabase(
            f"Refusing to run the tests: they TRUNCATE every table, and DATABASE_URL points at "
            f"non-local host(s) {remote}. Use a throwaway local PostgreSQL "
            f"(allowed hosts: {sorted(LOCAL_TEST_DB_HOSTS)}). There is no override."
        )
