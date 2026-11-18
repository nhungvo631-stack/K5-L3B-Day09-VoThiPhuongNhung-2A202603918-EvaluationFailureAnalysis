"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _make_decide(budget: Budget, trace: Trace, claim_id: str, seed: int):
    """ReAct policy. Reads only structured tool results; ticket text never drives money."""
    facts: dict[str, Any] = {}
    step = 0

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        nonlocal step
        step += 1
        # run_react drops earlier results, so keep our own memory.
        if "last_tool" in seen:
            facts[seen["last_tool"]] = seen["last_result"]
        # One model call per step keeps cost comparable. Prompt carries no row data.
        complete(budget, seed=seed, purpose="react", prompt=f"step={step} last={seen.get('last_tool')}")

        claim = facts.get("get_claim_view")
        if claim is None:
            action = {"tool": "get_claim_view", "args": {"claim_id": claim_id}}
        elif not claim["found"]:
            action = {"final": {"status": "failed", "error_reason": "unknown_claim"}}
        elif not claim["order_id"]:
            action = {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}
        elif "lookup_order" not in facts:
            action = {"tool": "lookup_order",
                      "args": {"order_id": claim["order_id"], "principal_id": claim["principal_id"]}}
        elif not facts["lookup_order"]["visible"]:
            action = {"final": {"status": "escalated", "error_reason": facts["lookup_order"]["reason"]}}
        elif "lookup_refund_history" not in facts:
            action = {"tool": "lookup_refund_history",
                      "args": {"order_id": claim["order_id"], "principal_id": claim["principal_id"]}}
        elif "compute_compensation" not in facts:
            # Order row from the DB, never the ticket's claimed delay.
            action = {"tool": "compute_compensation", "args": {"order": facts["lookup_order"]["order"]}}
        else:
            action = {"final": {"status": "quoted", "quote": facts["compute_compensation"]}}

        # Trace only the tool name / final status — no ticket, no raw rows.
        trace.add("react_step", {"step": step, "action": action.get("tool") or action["final"]["status"]})
        return action

    return decide, facts


def _run(conn, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    run_id = make_run_id(SHAPE, claim_id, seed)
    trace = Trace(run_id)

    def done(status: str, proposal: int = 0, reason: str | None = None) -> RunResult:
        complete(budget, seed=seed, purpose="draft", prompt=status)
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(conn, shape=SHAPE, claim_id=claim_id, seed=seed, status=status,
                      proposal_amount=proposal, budget=budget, trace=trace, error_reason=reason)

    decide, facts = _make_decide(budget, trace, claim_id, seed)
    out = run_react(conn, budget, observation={"claim": {"claim_id": claim_id}},
                    decide=decide, max_steps=MAX_STEPS)
    final = out["final"]

    if out["stopped"] == "step_cap" or final["status"] == "failed":
        return done("failed", reason=final.get("error_reason"))
    if final["status"] in ("needs_info", "escalated"):
        return done(final["status"], reason=final.get("error_reason"))

    # Allowlisted views only (lookup_order / lookup_refund_history already drop PII).
    trace.add("order", facts["lookup_order"]["order"])
    trace.add("refund_history", {"refunded_vnd": facts["lookup_refund_history"].get("refunded_vnd", 0)})
    quote = final["quote"]
    trace.add("quote", quote)
    proposal = int(quote["amount_vnd"])
    if proposal <= 0:
        return done("denied", reason=quote.get("reason"))

    # Host is the only writer. Full quote in; host subtracts earlier refunds.
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    if outcome["ok"]:
        return done("resolved", proposal)
    return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
