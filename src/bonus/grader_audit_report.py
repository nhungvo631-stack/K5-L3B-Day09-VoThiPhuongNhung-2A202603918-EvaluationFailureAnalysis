"""Bonus B7: run every metamorphic relation on the three candidate graders, write a JSON table.

    python -m bonus.grader_audit_report --out reports/bonus_grader_audit.json

Each cell says whether the relation holds for that grader and, if not, which keys moved
and by how much. Numbers come from running the graders, never typed by hand.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import random
from pathlib import Path
from typing import Any

from lab8.compensation import quote

FIXTURES = Path(__file__).resolve().parents[1] / "grader_audit" / "fixtures"
VARIANTS = ["grader_a", "grader_b", "grader_c"]
RATES = ["pass_rate", "pass_5", "seed_pass_rates", "seed_variance", "cost_per_success_vnd",
         "mean_steps", "mean_model_calls", "mean_tool_calls"]
TOTALS = ["trials", "graded_trials", "successes", "total_simulated_cost_vnd"]


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _same(x: Any, y: Any) -> bool:
    if isinstance(x, dict) and isinstance(y, dict):
        return x.keys() == y.keys() and all(_same(x[k], y[k]) for k in x)
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9)
    return x == y


def _compare(a: dict, b: dict, *, same: list[str], doubled: list[str] = ()) -> list[dict[str, Any]]:
    """Keys that broke the relation, with the numbers before and after."""
    broken = []
    for shape in a:
        for key in same:
            if not _same(a[shape][key], b[shape][key]):
                broken.append({"shape": shape, "key": key, "a": a[shape][key], "b": b[shape][key], "expected": a[shape][key]})
        for key in doubled:
            if not _same(2 * a[shape][key], b[shape][key]):
                broken.append({"shape": shape, "key": key, "a": a[shape][key], "b": b[shape][key], "expected": 2 * a[shape][key]})
    return broken


def infra(summarize) -> list[dict[str, Any]]:
    fx = _fixture("metamorphic_infra.json")
    return _compare(summarize(fx["a"]), summarize(fx["b"]), same=["pass_rate"])


def duplicate(summarize) -> list[dict[str, Any]]:
    fx = _fixture("metamorphic_duplicate.json")
    return _compare(summarize(fx["a"]), summarize(fx["b"]), same=RATES, doubled=TOTALS)


def shuffled(summarize) -> list[dict[str, Any]]:
    """New relation: reordering the trial list must not change any number."""
    trials = _fixture("metamorphic_infra.json")["b"]
    reordered = list(reversed(trials))
    random.Random(7).shuffle(reordered)
    return _compare(summarize(trials), summarize(reordered), same=RATES + TOTALS)


RELATIONS = {
    "infra_errors_do_not_move_pass_rate": infra,
    "duplicated_list_keeps_rates_doubles_totals": duplicate,
    "shuffled_trials_give_same_report (new)": shuffled,
}


def delay_2_vs_3() -> dict[str, Any]:
    """Business rule, independent of the graders. Expected values written from business_rules.md."""
    fx = _fixture("metamorphic_claim_delay.json")
    got = {k: quote(fx[k]["order"], fx["policies"], as_of=fx["as_of"]).amount_vnd for k in ("a", "b")}
    expected = {"a": 0, "b": fx["b"]["order"]["shipping_fee_vnd"]}
    return {"delay_days": {k: fx[k]["order"]["delay_days"] for k in ("a", "b")},
            "amount_vnd": got, "expected_vnd": expected, "holds": got == expected}


def build() -> dict[str, Any]:
    table = {}
    for variant in VARIANTS:
        summarize = importlib.import_module(f"grader_audit.{variant}").summarize
        table[variant] = {}
        for name, relation in RELATIONS.items():
            broken = relation(summarize)
            table[variant][name] = {"holds": not broken, "broken": broken}
    return {
        "run_id": "B7-grader-audit-v1",
        "fixtures": sorted(p.name for p in FIXTURES.glob("*.json")),
        "variants": VARIANTS,
        "relations": list(RELATIONS),
        "table": table,
        "business_rule": {"delay_2_vs_3": delay_2_vs_3()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="reports/bonus_grader_audit.json")
    args = parser.parse_args()
    report = build()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    width = max(len(r) for r in RELATIONS)
    print(f"{'relation':<{width}}  " + "  ".join(f"{v:<8}" for v in VARIANTS))
    for name in RELATIONS:
        cells = ["ok" if report["table"][v][name]["holds"] else "BROKEN" for v in VARIANTS]
        print(f"{name:<{width}}  " + "  ".join(f"{c:<8}" for c in cells))
    print(f"delay_2_vs_3 (business rule): {'ok' if report['business_rule']['delay_2_vs_3']['holds'] else 'BROKEN'}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
