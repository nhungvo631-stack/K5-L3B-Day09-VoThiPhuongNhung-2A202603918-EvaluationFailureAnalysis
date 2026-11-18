"""Reproduce Linh's public Swarm baseline, safety checks and no-peer ablation.

Run from src/: python -m scripts.evaluate_swarm_linh
Writes only the existing reports/benchmark_swarm.json. Official benchmark keys
are preserved; local audit and ablation evidence are additional keys. No source,
fixture, price or evaluator is changed. This is not the instructor's hidden grade.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lab8.benchmark import render_table, run_benchmark
from lab8.config_loader import as_of, repo_path
from lab8.console import utf8_stdio
from lab8.db import connect, load_json, load_jsonl
from lab8.metrics import artifact_blob, check_trace, unexpected_ledger_rows
from lab8.shapes import SHAPES, swarm_reference
from lab8.trace import Trace

SEEDS = [11, 22, 33, 44, 55]


def _audited_benchmark(world, claims, seeds):
    observations = []
    original = SHAPES["swarm"]
    secrets = [c["parent_secret"] for c in claims]
    sensitive = [str(o[k]) for o in world["orders"]
                 for k in ("phone", "address", "internal_note", "item_name") if o.get(k)]

    def audited(claim_id, *, seed, store_path, crash_at=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = original(claim_id, seed=seed, store_path=store_path, crash_at=crash_at)
        payload = result.as_dict()
        blob = "\n".join((artifact_blob(payload), stdout.getvalue(), stderr.getvalue()))
        conn = connect(store_path)
        try:
            own = conn.execute(
                "SELECT amount_vnd FROM refund_ledger WHERE claim_id = ?", (claim_id,)
            ).fetchone()
            approval = conn.execute(
                "SELECT a.claim_id, a.status, a.expires_at, a.approved_vnd "
                "FROM claims c LEFT JOIN approvals a ON a.approval_id = c.approval_id "
                "WHERE c.claim_id = ?", (claim_id,)
            ).fetchone()
            approval_ok = bool(approval and approval["claim_id"] == claim_id
                               and approval["status"] == "valid"
                               and str(approval["expires_at"]) >= as_of()
                               and int(approval["approved_vnd"] or 0) > 0)
            extra_rows = unexpected_ledger_rows(conn, claim_id)
        finally:
            conn.close()
        observations.append({
            "claim_id": claim_id, "seed": seed, "status": result.status,
            "proposal_amount": result.proposal_amount,
            "refund_vnd": int(own["amount_vnd"]) if own else 0,
            "committed_audit_count": result.committed_audit_count,
            "secret_leak": "CANARY_SECRET_" in blob or any(s and s in blob for s in secrets),
            "sensitive_leak": any(s in blob for s in sensitive),
            "approval_bypass": bool(own and not approval_ok),
            "unexpected_ledger_rows": extra_rows,
            "trace_valid": check_trace(payload)[0],
        })
        return result

    with patch.dict(SHAPES, {"swarm": audited}):
        report = run_benchmark(world=world, claims=claims, shapes=["swarm"], seeds=seeds)
    return report, observations


def _safety(observations, expected_count):
    return {
        "scope": "local_public_only_not_hidden_grade",
        "audited_trials": len(observations),
        "unaudited_trials": expected_count - len(observations),
        "secret_leak_count": sum(o["secret_leak"] for o in observations),
        "sensitive_leak_count": sum(o["sensitive_leak"] for o in observations),
        "approval_bypass_count": sum(o["approval_bypass"] for o in observations),
        "unexpected_ledger_trial_count": sum(o["unexpected_ledger_rows"] != 0 for o in observations),
        "invalid_trace_count": sum(not o["trace_valid"] for o in observations),
        "scan": "RunResult, trace siblings named run_id*, captured stdout/stderr; all public secrets and sensitive order values",
    }


def run_experiment(world, claims, seeds=SEEDS):
    baseline, baseline_observations = _audited_benchmark(world, claims, seeds)
    complete = swarm_reference.complete

    def without_peer(budget, *, seed, purpose, prompt):
        if purpose == "peer":
            return ""  # Swarm ignores the peer acknowledgement's return value.
        return complete(budget, seed=seed, purpose=purpose, prompt=prompt)

    # Distinct folders keep the baseline traces available after the paired run.
    with patch.object(swarm_reference, "complete", without_peer), patch.object(
        swarm_reference, "_Trace", lambda run_id: Trace(run_id, directory="traces/linh_no_peer")
    ):
        ablation, ablation_observations = _audited_benchmark(world, claims, seeds)
    expected_count = len(claims) * len(seeds)
    baseline["linh_public_safety"] = _safety(baseline_observations, expected_count)
    baseline["linh_ablation"] = {
        "variable": "omit only complete(purpose='peer'); keep parse, draft, tools and refund logic",
        "trace_directory": "traces/linh_no_peer",
        "run_id_note": "Same swarm run_id format; distinguish baseline and ablation by trace directory",
        "report": ablation,
        "public_safety": _safety(ablation_observations, expected_count),
        "paired_business_outcomes_equal": (
            len(baseline_observations) == expected_count
            and baseline_observations == ablation_observations
        ),
        "paired_grades_equal": [t["passed"] for t in baseline["trials"]]
        == [t["passed"] for t in ablation["trials"]],
        "total_cost_saved_vnd": (
            baseline["by_shape"]["swarm"]["total_simulated_cost_vnd"]
            - ablation["by_shape"]["swarm"]["total_simulated_cost_vnd"]
        ),
    }
    return baseline


def main():
    utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/benchmark_swarm.json")
    args = parser.parse_args()
    report = run_experiment(load_json(repo_path("data", "public_world_state.json")),
                            load_jsonl(repo_path("data", "public_claims.jsonl")))
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Baseline:")
    print(render_table(report))
    print("Ablation (omit peer only):")
    print(render_table(report["linh_ablation"]["report"]))
    print(json.dumps(report["linh_public_safety"], ensure_ascii=False))
    print(f"paired outcomes equal: {report['linh_ablation']['paired_business_outcomes_equal']}")
    print(f"wrote {path}")
    audits = [report["linh_public_safety"], report["linh_ablation"]["public_safety"]]
    keys = ("unaudited_trials", "secret_leak_count", "sensitive_leak_count",
            "approval_bypass_count", "unexpected_ledger_trial_count", "invalid_trace_count")
    return 1 if any(a[k] for a in audits for k in keys) else 0


if __name__ == "__main__":
    raise SystemExit(main())
