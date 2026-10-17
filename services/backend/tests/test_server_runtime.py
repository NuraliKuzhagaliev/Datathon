import json

import pytest
from jsonschema import ValidationError

from start_team_server import runtime_plan


def test_server_refuses_bundle_path_escape(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (tmp_path / "outside.exe").write_bytes(b"synthetic non-executable test file")
    (bundle / "launch.json").write_text(
        json.dumps(
            {
                "contract_version": "1.0.0",
                "executable": "../outside.exe",
                "cwd": ".",
                "args_prefix": ["-s"],
                "env": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises((ValueError, ValidationError)):
        runtime_plan(bundle)


def test_server_refuses_credentials_baked_into_bundle(tmp_path):
    (tmp_path / "python.exe").write_bytes(b"synthetic non-executable test file")
    (tmp_path / "launch.json").write_text(
        json.dumps(
            {
                "contract_version": "1.0.0",
                "executable": "python.exe",
                "cwd": ".",
                "args_prefix": ["-s"],
                "env": {"CASHPROOF_API_KEY": "synthetic-not-a-live-key"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="credentials"):
        runtime_plan(tmp_path)


def test_server_refuses_code_in_interpreter_prefix(tmp_path):
    (tmp_path / "launch.json").write_text(
        json.dumps(
            {
                "contract_version": "1.0.0",
                "executable": "python.exe",
                "cwd": ".",
                "args_prefix": ["-c", "print('synthetic')"],
                "env": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="interpreter flags"):
        runtime_plan(tmp_path)
