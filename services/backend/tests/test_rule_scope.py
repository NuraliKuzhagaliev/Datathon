import hashlib
from pathlib import Path

from cashproof.rules import Registry


def test_storage_scope_does_not_require_a_later_customer_and_stays_disabled():
    path = Path(__file__).resolve().parents[3] / "assets/rules/registry.json"
    registry = Registry(path)
    rule = registry.rules["NB231-20-STORAGE"]
    assert set(rule["predicates"]) == {
        "earlier_receipt_closed",
        "same_cash_exposed",
        "not_internal_handling",
    }
    assert "next_receipt_ongoing" not in rule["candidate_triggers"]
    assert not rule["public"]["enabled"]
    assert "NB231-20-STORAGE" not in registry.enabled
    assert (
        hashlib.sha256((path.parent / rule["snapshot"]).read_bytes()).hexdigest()
        == rule["public"]["source_sha256"]
    )
