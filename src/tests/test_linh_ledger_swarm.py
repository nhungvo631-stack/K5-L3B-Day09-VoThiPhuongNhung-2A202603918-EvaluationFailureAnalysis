"""Linh's regression evidence: persisted refunds, approval boundaries and Swarm.

Fixtures are modified only in a temporary test database. Production host, shapes,
public fixtures, metrics and prices stay unchanged.
"""

import json
import time
from pathlib import Path

import pytest

from lab8.config_loader import as_of
from lab8.db import connect
from lab8.durability import InjectedCrash, committed_audit_count, get_refund, issue_refund
from lab8.metrics import artifact_blob, check_trace, trial_pass
from lab8.shapes import SHAPES, swarm_reference
from scripts.evaluate_swarm_linh import run_experiment
from tests.conftest import BY_ID, CLAIMS, WORLD


@pytest.mark.parametrize("point", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"])
@pytest.mark.parametrize("claim_id,quote,paid", [("C-008", 35000, 20000), ("C-014", 150000, 120000)])
def test_capped_refund_survives_reopen_and_multiple_retries(public_db, point, claim_id, quote, paid):
    with pytest.raises(InjectedCrash):
        swarm_reference.run_claim(claim_id, seed=11, store_path=str(public_db), crash_at=point)
    conn = connect(public_db)
    try:
        effect = get_refund(conn, claim_id)
        assert (effect is None) == (point == "before_effect")
        checkpoint = conn.execute("SELECT 1 FROM checkpoints WHERE claim_id = ?", (claim_id,)).fetchone()
        assert (checkpoint is not None) == (point == "after_checkpoint")
    finally:
        conn.close()
    for _ in range(3):
        started = time.time()
        result = swarm_reference.run_claim(claim_id, seed=11, store_path=str(public_db))
        conn = connect(public_db)
        try:
            assert trial_pass(result.as_dict(), BY_ID[claim_id]["expected"], conn, started_at=started) == (True, "ok")
            assert result.proposal_amount == quote
            assert get_refund(conn, claim_id)["amount_vnd"] == paid
            assert committed_audit_count(conn, claim_id) == 1
            assert conn.execute("SELECT COUNT(*) FROM refund_ledger WHERE claim_id = ?", (claim_id,)).fetchone()[0] == 1
        finally:
            conn.close()


@pytest.mark.parametrize("expires,expected", [(as_of(), "resolved"), ("2026-11-14", "denied")])
def test_swarm_approval_expiry_boundary(public_db, expires, expected):
    conn = connect(public_db)
    try:
        conn.execute("UPDATE approvals SET expires_at = ? WHERE approval_id = 'A-001'", (expires,))
        conn.commit()
    finally:
        conn.close()
    result = swarm_reference.run_claim("C-001", seed=11, store_path=str(public_db))
    assert result.status == expected
    assert result.proposal_amount == 35000
    assert len(result.refund_effects) == int(expected == "resolved")
    if expected == "denied":
        assert result.error_reason == "approval_expired"


@pytest.mark.parametrize("change,reason", [
    ("UPDATE claims SET approval_id = NULL WHERE claim_id = 'C-001'", "missing_approval"),
    ("UPDATE approvals SET approved_vnd = 0 WHERE approval_id = 'A-001'", "non_positive_amount"),
    ("UPDATE approvals SET status = 'revoked' WHERE approval_id = 'A-001'", "approval_revoked"),
    ("UPDATE claims SET approval_id = 'A-008' WHERE claim_id = 'C-001'", "approval_claim_mismatch"),
])
def test_swarm_invalid_approval_is_denied_on_every_retry(public_db, change, reason):
    conn = connect(public_db)
    try:
        conn.execute(change)
        conn.commit()
    finally:
        conn.close()
    for _ in range(2):
        result = swarm_reference.run_claim("C-001", seed=11, store_path=str(public_db))
        assert (result.status, result.error_reason, result.proposal_amount) == ("denied", reason, 35000)
        assert result.refund_effects == []
        assert result.committed_audit_count == 0
    conn = connect(public_db)
    try:
        rows = conn.execute("SELECT details_json FROM audit_events WHERE claim_id = 'C-001' AND event_type = 'policy_denied'").fetchall()
        assert [json.loads(r[0])["reason"] for r in rows] == [reason]
    finally:
        conn.close()


def test_topup_crash_then_changed_quote_conflicts_without_rewriting_payment(public_db):
    conn = connect(public_db)
    try:
        with pytest.raises(InjectedCrash):
            issue_refund(conn, "C-014", 150000, crash_at="after_effect_before_checkpoint")
    finally:
        conn.close()
    conn = connect(public_db)
    try:
        conflict = issue_refund(conn, "C-014", 140000)
        assert conflict["conflict"] and conflict["reason"] == "amount_conflict"
        assert get_refund(conn, "C-014")["amount_vnd"] == 120000
        assert committed_audit_count(conn, "C-014") == 1
        assert issue_refund(conn, "C-014", 150000)["reason"] == "idempotent_replay"
    finally:
        conn.close()


def test_revoking_approval_after_payment_blocks_retry_without_erasing_history(public_db):
    conn = connect(public_db)
    try:
        assert issue_refund(conn, "C-001", 35000)["ok"]
        conn.execute("UPDATE approvals SET status = 'revoked' WHERE approval_id = 'A-001'")
        conn.commit()
        assert issue_refund(conn, "C-001", 35000)["reason"] == "approval_revoked"
        assert get_refund(conn, "C-001")["amount_vnd"] == 35000
        assert committed_audit_count(conn, "C-001") == 1
    finally:
        conn.close()


@pytest.mark.parametrize("claim_id", ["C-001", "C-004", "C-005"])
def test_swarm_trace_and_console_hide_all_public_sensitive_values(public_db, capsys, claim_id):
    started = time.time()
    result = swarm_reference.run_claim(claim_id, seed=55, store_path=str(public_db)).as_dict()
    assert check_trace(result, started_at=started) == (True, "ok")
    captured = capsys.readouterr()
    blob = artifact_blob(result) + captured.out + captured.err
    forbidden = [c["parent_secret"] for c in CLAIMS]
    forbidden += [o[k] for o in WORLD["orders"] for k in ("phone", "address", "internal_note", "item_name")]
    assert not any(s in blob for s in forbidden)
    assert "CANARY_SECRET_" not in blob


def test_no_peer_ablation_preserves_decisions_and_restores_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_complete, original_trace, original_shape = swarm_reference.complete, swarm_reference._Trace, SHAPES["swarm"]
    claims = [BY_ID["C-001"], BY_ID["C-002"]]
    report = run_experiment(WORLD, claims, seeds=[11, 55])
    ablation = report["linh_ablation"]
    assert ablation["paired_business_outcomes_equal"]
    assert ablation["paired_grades_equal"]
    # Keep the reference weakness: removing unused peer text cannot fix T02.
    assert report["by_shape"]["swarm"]["pass_rate"] == 0.75
    assert ablation["report"]["by_shape"]["swarm"]["pass_rate"] == 0.75
    assert ablation["total_cost_saved_vnd"] > 0
    assert report["by_shape"]["swarm"]["mean_model_calls"] == 3
    assert ablation["report"]["by_shape"]["swarm"]["mean_model_calls"] == 2
    for audit in (report["linh_public_safety"], ablation["public_safety"]):
        assert audit["audited_trials"] == 4
        assert all(audit[k] == 0 for k in ("unaudited_trials", "secret_leak_count", "sensitive_leak_count", "approval_bypass_count", "unexpected_ledger_trial_count", "invalid_trace_count"))
    assert swarm_reference.complete is original_complete
    assert swarm_reference._Trace is original_trace
    assert SHAPES["swarm"] is original_shape
    assert Path("traces/R-swarm-C-002-s55.json").is_file()
    assert Path("traces/linh_no_peer/R-swarm-C-002-s55.json").is_file()
