from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def test_migration_history_has_single_head():
    script = ScriptDirectory.from_config(
        Config(str(PROJECT_ROOT / "alembic.ini"))
    )

    assert script.get_heads() == ["20261106_0002"]

    auth_revision = script.get_revision("20261106_0002")
    assert auth_revision is not None
    assert auth_revision.down_revision == "20261024_0001"

    memory_revision = script.get_revision("20261024_0001")
    assert memory_revision is not None
    assert memory_revision.down_revision is None


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for destructive migration testing",
)
def test_upgrade_downgrade_and_reupgrade_on_isolated_database():
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}

    def alembic(*args: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
        )

    alembic("upgrade", "head")
    alembic("downgrade", "base")
    alembic("upgrade", "head")
