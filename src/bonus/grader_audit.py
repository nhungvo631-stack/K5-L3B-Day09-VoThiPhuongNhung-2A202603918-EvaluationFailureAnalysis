from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
from typing import Any

from lab8.compensation import quote

GRADERS = ("grader_a", "grader_b", "grader_c")
FIXTURES = Path(__file__).resolve().parents[1] / "grader_audit" / "fixtures"
RATIO_FIELDS = (
    "pass_rate",
    "pass_5",
    "seed_pass_rates",
    "seed_variance",
    "seed_min",
    "seed_max",
    "cost_per_success_vnd",
    "mean_steps",
    "p95_steps",
    "mean_model_calls",
    "mean_tool_calls",
)
TOTAL_FIELDS = ("trials", "graded_trials", "successes", "total_simulated_cost_vnd")


def _read_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES / name
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _grader(name: str):
    if name not in GRADERS:
        raise ValueError(f"unknown grader: {name}")
    return importlib.import_module(f"grader_audit.{name}")


def _close(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_close(left[key], right[key]) for key in left)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    return left == right


def _infra_result(module, fixture: dict[str, Any]) -> dict[str, Any]:
    before = module.summarize(fixture["a"])["workflow"]
    after = module.summarize(fixture["b"])["workflow"]
    delta = after["pass_rate"] - before["pass_rate"]
    return {
        "holds": math.isclose(delta, 0.0, abs_tol=1e-12),
        "pass_rate_before": before["pass_rate"],
        "pass_rate_after": after["pass_rate"],
        "pass_rate_delta": delta,
        "graded_trials_before": before["graded_trials"],
        "graded_trials_after": after["graded_trials"],
    }


def _duplicate_result(module, fixture: dict[str, Any]) -> dict[str, Any]:
    before = module.summarize(fixture["a"])["workflow"]
    after = module.summarize(fixture["b"])["workflow"]
    ratio_checks = {
        field: _close(before[field], after[field])
        for field in RATIO_FIELDS
    }
    total_checks = {
        field: math.isclose(
            float(after[field]),
            2.0 * float(before[field]),
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        for field in TOTAL_FIELDS
    }
    return {
        "holds": all(ratio_checks.values()) and all(total_checks.values()),
        "ratio_checks": ratio_checks,
        "total_checks": total_checks,
        "ratio_values": {
            field: {"before": before[field], "after": after[field]}
            for field in RATIO_FIELDS
        },
        "total_values": {
            field: {
                "before": before[field],
                "after": after[field],
                "expected_after": 2 * before[field],
            }
            for field in TOTAL_FIELDS
        },
    }


def _shape_isolation_result(module, fixture: dict[str, Any]) -> dict[str, Any]:
    workflow_trials = fixture["a"]
    unrelated_trials = [
        {
            "shape": "swarm",
            "claim_id": "C-OTHER",
            "seed": 11,
            "passed": False,
            "cost_estimate": 1000.0,
            "steps": 100,
            "model_calls": 50,
            "tool_calls": 50,
            "reason": "unrelated_shape",
            "infra_error": False,
        }
    ]
    before = module.summarize(workflow_trials)["workflow"]
    after = module.summarize(workflow_trials + unrelated_trials)["workflow"]
    changed_fields = [
        key for key in before
        if not _close(before[key], after[key])
    ]
    return {
        "holds": not changed_fields,
        "changed_fields": changed_fields,
        "workflow_pass_rate_before": before["pass_rate"],
        "workflow_pass_rate_after": after["pass_rate"],
    }


def _claim_delay_result() -> dict[str, Any]:
    fixture = _read_fixture("metamorphic_claim_delay.json")
    quotes = {}
    for label in ("a", "b"):
        trial = fixture[label]
        result = quote(trial["order"], fixture["policies"], as_of=fixture["as_of"])
        quotes[label] = {
            "delay_days": trial["order"]["delay_days"],
            "amount_vnd": result.amount_vnd,
            "reason": result.reason,
        }
    return {
        "relation": fixture["relation"],
        "quotes": quotes,
        "holds": quotes["a"]["amount_vnd"] == 0
        and quotes["b"]["amount_vnd"] == 35000,
    }


def build_audit() -> dict[str, Any]:
    infra_fixture = _read_fixture("metamorphic_infra.json")
    duplicate_fixture = _read_fixture("metamorphic_duplicate.json")
    results = {}
    for name in GRADERS:
        module = _grader(name)
        results[name] = {
            "infrastructure_errors_excluded": _infra_result(module, infra_fixture),
            "duplicate_input_scales_totals_only": _duplicate_result(module, duplicate_fixture),
            "unrelated_shape_isolation": _shape_isolation_result(module, duplicate_fixture),
        }
    return {
        "topic": "B7",
        "claim_delay_business_rule": _claim_delay_result(),
        "graders": results,
        "interpretation": {
            "infrastructure_errors_scored_as_failures": [
                name for name in GRADERS
                if not results[name]["infrastructure_errors_excluded"]["holds"]
            ],
            "duplicate_input_breaks_invariants": [
                name for name in GRADERS
                if not results[name]["duplicate_input_scales_totals_only"]["holds"]
            ],
            "duplicate_input_changes_pass_5": [
                name for name in GRADERS
                if not results[name]["duplicate_input_scales_totals_only"]["ratio_checks"]["pass_5"]
            ],
            "duplicate_input_changes_cost_accounting": [
                name for name in GRADERS
                if (
                    not results[name]["duplicate_input_scales_totals_only"]["ratio_checks"][
                        "cost_per_success_vnd"
                    ]
                    or not results[name]["duplicate_input_scales_totals_only"]["total_checks"][
                        "total_simulated_cost_vnd"
                    ]
                )
            ],
            "cross_shape_contamination": [
                name for name in GRADERS
                if not results[name]["unrelated_shape_isolation"]["holds"]
            ],
        },
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    # Keep the isolation audit separate from the permutation audit in PR #14.
    output = root / "reports" / "bonus_grader_isolation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_audit(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
