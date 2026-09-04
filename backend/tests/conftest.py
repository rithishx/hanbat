"""Shared fixtures.

`api_client` lives here rather than in one test module so that new suites can
exercise the real app without each one rebuilding the same throwaway database.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def api_client():
    """The real app, on its own database, loaded from the real content files."""
    tmp = tempfile.mkdtemp(prefix="hanbat-fixture-")
    os.environ["HANBAT_DATA_DIR"] = tmp
    os.environ["HANBAT_DB"] = str(Path(tmp) / "fixture.sqlite3")

    import importlib
    from app import config, db
    importlib.reload(config)
    importlib.reload(db)
    from app import store
    importlib.reload(store)
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
