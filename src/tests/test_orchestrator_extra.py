"""Extra tests for shape C (orchestrator): CP3 handoff, trace and crash/retry.

These run in the default host gate (no `student` marker), so they must stay green.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab8.db import connect, init_store
from lab8.durability import InjectedCrash
from lab8.handoff import ALLOWED_FIELDS, READONLY_TOOLS, WRITE_TOOLS
from lab8.shapes.orchestrator import run_claim
from tests.conftest import CLAIMS, WORLD

CLAIM_IDS = [row["claim_id"] for row in CLAIMS]
SEEDS = [11, 55]
# Anything from the parent context or the order row that must never reach a trace.
FORBIDDEN = ["CANARY_SECRET_", "parent_secret", "raw_headers", "Bearer ", "CANARY_INTERNAL_", "0901", "Le Loi", "SECRET_ITEM"]


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """Trace writes to ./traces. Keep test traces out of src/traces."""
    monkeypatch.chdir(tmp_path)


def _store(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    init_store(path, WORLD, CLAIMS).close()
    return path


def _trace(result) -> dict:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("claim_id", CLAIM_IDS)
@pytest.mark.parametrize("seed", SEEDS)
def test_trace_is_valid_and_has_no_secret_or_pii(tmp_path, claim_id, seed):
    store = _store(tmp_path, f"{claim_id}-{seed}.sqlite")
    result = run_claim(claim_id, seed=seed, store_path=str(store))
    trace = _trace(result)
    assert trace["run_id"] == result.run_id
    assert isinstance(trace["events"], list) and trace["events"]
    blob = json.dumps(trace, ensure_ascii=False) + json.dumps(result.as_dict(), ensure_ascii=False)
    for needle in FORBIDDEN:
        assert needle not in blob, f"{needle!r} leaked for {claim_id}"
    # The raw ticket is parent context. It must not be copied into the trace either.
    ticket = next(row["ticket"] for row in CLAIMS if row["claim_id"] == claim_id)
    assert ticket not in blob


@pytest.mark.parametrize("claim_id", CLAIM_IDS)
def test_handoff_in_trace_is_allowlisted_and_read_only(tmp_path, claim_id):
    store = _store(tmp_path, f"{claim_id}.sqlite")
    result = run_claim(claim_id, seed=11, store_path=str(store))
    handoffs = [e["payload"] for e in _trace(result)["events"] if e["kind"] == "handoff"]
    order_id = next(row["order_id"] for row in CLAIMS if row["claim_id"] == claim_id)
    if not order_id:
        # needs_info returns before any handoff is built.
        assert handoffs == []
        return
    assert len(handoffs) == 1
    handoff = handoffs[0]
    assert set(handoff) <= ALLOWED_FIELDS
    assert handoff["claim_id"] == claim_id
    assert set(handoff["allowed_tools"]) <= READONLY_TOOLS
    assert not set(handoff["allowed_tools"]) & WRITE_TOOLS


def test_retry_after_crash_keeps_one_refund_and_one_audit(tmp_path):
    store = _store(tmp_path, "crash.sqlite")
    with pytest.raises(InjectedCrash):
        run_claim("C-012", seed=11, store_path=str(store), crash_at="after_effect_before_checkpoint")
    resumed = run_claim("C-012", seed=11, store_path=str(store))
    conn = connect(store)
    try:
        rows = conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-012'").fetchone()["n"]
    finally:
        conn.close()
    assert resumed.status == "resolved"
    assert rows == 1
    assert resumed.committed_audit_count == 1
    assert len(resumed.refund_effects) == 1


@pytest.mark.parametrize("crash_at", ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"])
def test_crash_flushes_a_valid_trace_and_resume_is_single_refund(tmp_path, crash_at):
    store = _store(tmp_path, f"{crash_at}.sqlite")
    with pytest.raises(InjectedCrash):
        run_claim("C-001", seed=22, store_path=str(store), crash_at=crash_at)
    crashed = json.loads((Path("traces") / "R-orchestrator-C-001-s22.json").read_text(encoding="utf-8"))
    assert crashed["run_id"] == "R-orchestrator-C-001-s22"
    assert crashed["events"][-1]["kind"] == "crash"
    assert "CANARY_SECRET_" not in json.dumps(crashed)
    resumed = run_claim("C-001", seed=22, store_path=str(store))
    conn = connect(store)
    try:
        rows = conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = 'C-001'").fetchone()["n"]
    finally:
        conn.close()
    assert resumed.status == "resolved"
    assert rows == 1
    assert resumed.committed_audit_count == 1


def test_retry_with_same_claim_is_idempotent(tmp_path):
    store = _store(tmp_path, "retry.sqlite")
    first = run_claim("C-011", seed=11, store_path=str(store))
    second = run_claim("C-011", seed=11, store_path=str(store))
    assert first.status == second.status == "resolved"
    assert second.committed_audit_count == 1
    assert len(second.refund_effects) == 1


# ---------------------------------------------------------------------------
# CP4: approval, per-order cap, secrets. The host must refuse; the shape must not pay around it.
# ---------------------------------------------------------------------------

import copy


def _world_store(tmp_path: Path, name: str, *, approvals=None, claims=None) -> Path:
    world = copy.deepcopy(WORLD)
    if approvals is not None:
        world["approvals"] = approvals(world["approvals"])
    path = tmp_path / name
    init_store(path, world, claims if claims is not None else CLAIMS).close()
    return path


def _ledger_rows(store: Path, claim_id: str | None = None) -> int:
    conn = connect(store)
    try:
        if claim_id is None:
            # The world seeds two historical refunds (C-HIST-*). Count only rows written by this run.
            return conn.execute(
                "SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id NOT LIKE 'C-HIST-%'"
            ).fetchone()["n"]
        return conn.execute("SELECT COUNT(*) AS n FROM refund_ledger WHERE claim_id = ?", (claim_id,)).fetchone()["n"]
    finally:
        conn.close()


def _denied_reasons(store: Path, claim_id: str) -> list[str]:
    conn = connect(store)
    try:
        rows = conn.execute(
            "SELECT details_json FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(row["details_json"])["reason"] for row in rows]


def _change(approval_id: str, **fields):
    def apply(rows):
        for row in rows:
            if row["approval_id"] == approval_id:
                row.update(fields)
        return rows

    return apply


@pytest.mark.parametrize(
    "fields, reason",
    [
        ({"status": "revoked"}, "approval_revoked"),
        ({"expires_at": "2020-01-01"}, "approval_expired"),
        ({"approved_vnd": 0}, "non_positive_amount"),
        ({"claim_id": "C-999"}, "approval_claim_mismatch"),
    ],
)
def test_bad_approval_means_no_refund_and_a_policy_denied_audit(tmp_path, fields, reason):
    store = _world_store(tmp_path, "bad.sqlite", approvals=_change("A-001", **fields))
    result = run_claim("C-001", seed=11, store_path=str(store))
    assert result.status == "denied"
    assert result.proposal_amount == 35000  # the full quote, not the refused amount
    assert _ledger_rows(store) == 0
    assert result.refund_effects == []
    assert result.committed_audit_count == 0
    assert _denied_reasons(store, "C-001") == [reason]


def test_missing_approval_means_no_refund(tmp_path):
    claims = [dict(row, approval_id=None) if row["claim_id"] == "C-001" else row for row in CLAIMS]
    store = _world_store(tmp_path, "noappr.sqlite", claims=claims)
    result = run_claim("C-001", seed=11, store_path=str(store))
    assert result.status == "denied"
    assert _ledger_rows(store) == 0
    assert _denied_reasons(store, "C-001") == ["missing_approval"]


def test_borrowed_approval_from_another_claim_is_refused(tmp_path):
    """C-001 points at A-010, which was issued for C-010. Amount matches; the claim does not."""
    claims = [dict(row, approval_id="A-010") if row["claim_id"] == "C-001" else row for row in CLAIMS]
    store = _world_store(tmp_path, "borrowed.sqlite", claims=claims)
    result = run_claim("C-001", seed=11, store_path=str(store))
    assert result.status == "denied"
    assert _ledger_rows(store, "C-001") == 0
    assert _denied_reasons(store, "C-001") == ["approval_claim_mismatch"]


def test_approval_below_quote_pays_the_approved_amount_but_reports_full_quote(tmp_path):
    store = _world_store(tmp_path, "low.sqlite", approvals=_change("A-001", approved_vnd=10000))
    result = run_claim("C-001", seed=11, store_path=str(store))
    assert result.status == "resolved"
    assert result.proposal_amount == 35000
    assert [e["amount_vnd"] for e in result.refund_effects] == [10000]


def test_second_claim_on_same_order_is_capped_per_order(tmp_path):
    """C-001 and C-010 are both for O-107 (entitlement 35000). The order can only be paid once."""
    store = _world_store(tmp_path, "stack.sqlite")
    first = run_claim("C-001", seed=11, store_path=str(store))
    second = run_claim("C-010", seed=11, store_path=str(store))
    assert first.status == "resolved"
    assert second.status == "denied"
    assert second.proposal_amount == 35000
    assert _ledger_rows(store) == 1
    assert _denied_reasons(store, "C-010") == ["order_already_refunded"]


def test_ticket_text_cannot_raise_the_quote(tmp_path):
    """The ticket claims 5 days late (C-002) or says 'ignore policy' (C-009). Quote comes from the order row."""
    store = _world_store(tmp_path, "ticket.sqlite")
    for claim_id in ("C-002", "C-009", "C-006"):
        for seed in (11, 55):
            result = run_claim(claim_id, seed=seed, store_path=str(store))
            assert result.status == "denied" and result.proposal_amount == 0
    assert _ledger_rows(store) == 0


def test_no_secret_on_stdout(tmp_path, capsys):
    store = _world_store(tmp_path, "stdout.sqlite")
    for claim_id in CLAIM_IDS:
        run_claim(claim_id, seed=11, store_path=str(store))
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
