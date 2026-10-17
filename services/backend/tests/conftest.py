import hashlib
import json
from pathlib import Path
import sys
import pytest
from cashproof.config import Settings
from cashproof.rules import Registry

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from synthetic_clip import create


@pytest.fixture
def clip(tmp_path):
    return create(tmp_path / "синтетика с пробелом.MOV", rotated=True)


@pytest.fixture
def registry(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Synthetic test rule; has no legal force.")
    rules = []
    for id in ["TEST-A", "TEST-B"]:
        public = dict(
            rule_id=id,
            display_name=id,
            document_title="Synthetic test only",
            source_url="https://example.invalid/synthetic",
            clause="test",
            revision="1",
            effective_date="2020-01-01",
            applicability="Synthetic test fixture",
            exclusions=["Real videos"],
            enabled=True,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        rules.append(
            dict(
                public=public,
                predicates={"observed": "Visible synthetic condition"},
                context="Full synthetic sequence",
                snapshot="source.txt",
                template="Synthetic result, not a legal category.",
            )
        )
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"version": "test-1", "rules": rules}))
    return Registry(path)


@pytest.fixture
def settings(tmp_path, registry):
    return Settings(
        data_dir=tmp_path / "cases",
        rules_path=registry.path,
        operator_key="o" * 32,
        jury_key="j" * 32,
    )


class TestWorker:
    ready = True
    model_version = "test-only-injected"

    def start(self):
        pass

    def close(self):
        pass


@pytest.fixture
def client(settings):
    from fastapi.testclient import TestClient
    from cashproof.api import create_app

    with TestClient(create_app(settings, TestWorker())) as client:
        yield client
