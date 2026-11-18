"""Shape B: ReAct stays within 8 steps, uses only read tools, never trusts or traces the ticket."""

import json

import pytest

from lab8.handoff import READONLY_TOOLS
from lab8.shapes.single import MAX_STEPS, run_claim
from tests.conftest import BY_ID


@pytest.mark.parametrize("claim_id", ["C-001", "C-002", "C-014"])
def test_single_react_bounded_readonly_and_ticket_free(public_db, claim_id):
    result = run_claim(claim_id, seed=55, store_path=str(public_db))
    with open(result.trace_path, encoding="utf-8") as fh:
        trace = json.load(fh)
    steps = [e["payload"]["action"] for e in trace["events"] if e["kind"] == "react_step"]
    assert len(steps) <= MAX_STEPS == 8
    assert set(steps[:-1]) <= READONLY_TOOLS  # last step is the final status
    assert BY_ID[claim_id]["ticket"] not in json.dumps(trace, ensure_ascii=False)


def test_single_ignores_ticket_delay_on_seed_55(public_db):
    # C-002: ticket says 5 days late, order row says 2 -> must deny (swarm fails this).
    result = run_claim("C-002", seed=55, store_path=str(public_db))
    assert (result.status, result.proposal_amount, result.refund_effects) == ("denied", 0, [])
