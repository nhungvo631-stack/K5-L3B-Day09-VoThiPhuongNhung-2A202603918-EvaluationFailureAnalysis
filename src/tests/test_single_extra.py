"""Extra tests for shape B (single): host must refuse broken approvals and fully refunded orders.

The shape still sends the full quote to the host, so status is `denied`, proposal_amount
is the full quote, no ledger row is written, and the host records `policy_denied`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import connect, init_store
from lab8.shapes.single import run_claim
from tests.conftest import CLAIMS, WORLD


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """Trace writes to ./traces. Keep test traces out of src/traces."""
    monkeypatch.chdir(tmp_path)


def _store(tmp_path: Path, *sql: tuple) -> Path:
    path = tmp_path / "store.sqlite"
    conn = init_store(path, WORLD, CLAIMS)
    for stmt, args in sql:
        conn.execute(stmt, args)
    conn.commit()
    conn.close()
    return path


def _assert_host_denied(store: Path, claim_id: str, quote: int, reason: str, seed: int) -> None:
    result = run_claim(claim_id, seed=seed, store_path=str(store))
    assert (result.status, result.proposal_amount, result.refund_effects) == ("denied", quote, [])
    assert result.committed_audit_count == 0
    conn = connect(store)
    try:
        ledger = conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,)).fetchone()["n"]
        reasons = [
            json.loads(row["details_json"])["reason"]
            for row in conn.execute(
                "SELECT details_json FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
                (claim_id,),
            )
        ]
    finally:
        conn.close()
    assert ledger == 0
    assert reasons == [reason]


# C-001: order O-107, 4 days late, quote 35000, approval A-001. Break the approval in different ways.
BROKEN_APPROVALS = {
    "missing": (("UPDATE claims SET approval_id = NULL WHERE claim_id = 'C-001'", ()), "missing_approval"),
    "not_found": (("UPDATE claims SET approval_id = 'A-999' WHERE claim_id = 'C-001'", ()), "missing_approval"),
    "other_claim": (("UPDATE claims SET approval_id = 'A-010' WHERE claim_id = 'C-001'", ()), "approval_claim_mismatch"),
    "revoked": (("UPDATE approvals SET status = 'revoked' WHERE approval_id = 'A-001'", ()), "approval_revoked"),
    "expired": (("UPDATE approvals SET expires_at = '2020-01-01' WHERE approval_id = 'A-001'", ()), "approval_expired"),
    "zero_amount": (("UPDATE approvals SET approved_vnd = 0 WHERE approval_id = 'A-001'", ()), "non_positive_amount"),
}


@pytest.mark.parametrize("seed", [11, 55])
@pytest.mark.parametrize("case", BROKEN_APPROVALS)
def test_broken_approval_is_denied_by_host(tmp_path, case, seed):
    stmt, reason = BROKEN_APPROVALS[case]
    store = _store(tmp_path, stmt)
    _assert_host_denied(store, "C-001", 35000, reason, seed)


def test_borrowed_approval_does_not_pay_the_owner_claim_either(tmp_path):
    # C-001 points at C-010's approval. Nothing may be written under any claim.
    store = _store(tmp_path, ("UPDATE claims SET approval_id = 'A-010' WHERE claim_id = 'C-001'", ()))
    run_claim("C-001", seed=11, store_path=str(store))
    conn = connect(store)
    try:
        rows = conn.execute("SELECT claim_id FROM refund_ledger WHERE claim_id NOT LIKE 'C-HIST-%'").fetchall()
    finally:
        conn.close()
    assert rows == []


@pytest.mark.parametrize("seed", [11, 55])
def test_public_expired_approval_t07(tmp_path, seed):
    _assert_host_denied(_store(tmp_path), "C-007", 35000, "approval_expired", seed)


@pytest.mark.parametrize("seed", [11, 55])
def test_order_already_fully_refunded_t13(tmp_path, seed):
    # O-505 already got 35000 from an earlier claim. Ticket says "not received" -> still denied.
    _assert_host_denied(_store(tmp_path), "C-013", 35000, "order_already_refunded", seed)


def test_order_fully_refunded_by_this_flow_blocks_a_second_claim(tmp_path):
    # C-010 pays O-107 in full; then C-001 on the same order must be denied, not paid twice.
    store = _store(tmp_path)
    first = run_claim("C-010", seed=11, store_path=str(store))
    assert first.status == "resolved"
    _assert_host_denied(store, "C-001", 35000, "order_already_refunded", 11)
