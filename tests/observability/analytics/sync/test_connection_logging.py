# Copyright 2026 Geser Dugarov
# SPDX-License-Identifier: Apache-2.0
"""Which endpoint the operator is told about, and what is stripped out of it."""
from __future__ import annotations

import unittest

from orchestrator.observability.analytics.sync.redaction import redact_db_url
from tests.observability.analytics.sync.sync_fake_driver import FakeConnection
from tests.observability.analytics.sync.sync_test_support import (
    jsonl_log,
    sample_record,
    sync_capturing_logs,
)

_NETLOC_SECRET = "postgresql://u:secret@h:5432/db"

_QUERY_SECRET = "postgresql://h:5432/db?user=u&password=qs-secret"


class ConnectionLogTest(unittest.TestCase):
    """The connect is bracketed by a pair of lines so a remote-Postgres
    reachability problem surfaces immediately, and the URL in both is the
    redacted one -- whichever half of it the credentials were hiding in.
    """

    def test_the_connect_pair_names_a_redacted_url(self) -> None:
        with jsonl_log([sample_record()]) as path:
            _, log_lines = sync_capturing_logs(
                self, path, FakeConnection(), db_url=_NETLOC_SECRET,
            )
        joined = "\n".join(log_lines)
        self.assertIn("connecting to", joined)
        self.assertIn("connection established", joined)
        self.assertNotIn("secret", joined)
        # Host and port survive, so the operator can still tell which endpoint
        # answered.
        self.assertIn("***@h:5432", joined)

    def test_a_query_password_never_reaches_the_log(self) -> None:
        with jsonl_log([sample_record()]) as path:
            _, log_lines = sync_capturing_logs(
                self, path, FakeConnection(), db_url=_QUERY_SECRET,
            )
        joined = "\n".join(log_lines)
        self.assertNotIn("qs-secret", joined)
        self.assertIn("connection established", joined)


class RedactedUrlTest(unittest.TestCase):
    """Credentials collapse to `***` in both places libpq accepts them, while
    everything an operator needs to identify the endpoint passes through
    verbatim.
    """

    def test_a_url_without_credentials_passes_through(self) -> None:
        self.assertEqual(
            redact_db_url("postgresql://h:5432/db"), "postgresql://h:5432/db",
        )

    def test_a_user_with_no_password_is_stripped(self) -> None:
        self.assertIn("***@h", redact_db_url("postgresql://user@h/db"))

    def test_credential_parameters_are_redacted(self) -> None:
        # libpq accepts `?user=&password=`, so netloc-only redaction would leak
        # the password into the operator's stdout.
        redacted = redact_db_url("postgresql://h/db?user=u&password=secret&sslmode=require")
        self.assertNotIn("secret", redacted)
        self.assertNotIn("user=u", redacted)
        self.assertIn("password=", redacted)
        self.assertIn("***", redacted)
        # A non-credential parameter survives: the redacted URL still says
        # which SSL mode was configured.
        self.assertIn("sslmode=require", redacted)

    def test_the_ssl_key_password_is_redacted(self) -> None:
        # `sslpassword` decrypts the SSL client key: same threat model as the
        # password itself.
        redacted = redact_db_url("postgresql://h/db?sslpassword=ssl-secret")
        self.assertNotIn("ssl-secret", redacted)
        self.assertIn("sslpassword=", redacted)

    def test_parameter_names_ignore_case(self) -> None:
        # libpq treats them as case-insensitive, so `?PASSWORD=` must not slip
        # past the filter.
        self.assertNotIn("secret", redact_db_url("postgresql://h/db?PASSWORD=secret"))


if __name__ == "__main__":
    unittest.main()
