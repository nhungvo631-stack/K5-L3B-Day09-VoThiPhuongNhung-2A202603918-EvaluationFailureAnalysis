"""Bonus B7: audit three candidate `summarize` graders with metamorphic relations.

Each relation says how the output must (or must not) change when the input changes in a
known way. No absolute answer is needed. A variant that breaks a relation is wrong.
Known breaks are marked xfail(strict=True): the evidence stays in the suite, the host gate
stays green, and the test turns red if the variant ever stops breaking the relation.
"""

from __future__ import annotations

import importlib
import json
import random
from pathlib import Path

import pytest

from lab8.compensation import quote

FIXTURES = Path(__file__).resolve().parents[1] / "grader_audit" / "fixtures"
VARIANTS = ["grader_a", "grader_b", "grader_c"]

RATES = ["pass_rate", "seed_pass_rates", "seed_variance", "cost_per_success_vnd",
         "mean_steps", "mean_model_calls", "mean_tool_calls"]
TOTALS = ["trials", "graded_trials", "successes", "total_simulated_cost_vnd"]


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _summarize(variant: str):
    return importlib.import_module(f"grader_audit.{variant}").summarize


def _known_break(variant: str, broken: set[str], why: str):
    marks = [pytest.mark.xfail(strict=True, reason=why)] if variant in broken else []
    return pytest.param(variant, marks=marks, id=variant)


# Relation 1: infra trials (timeout, infra crash) are not wrong decisions by the shape.
@pytest.mark.parametrize("variant", [
    _known_break(v, {"grader_c"}, "counts infra trials as failed decisions (pass_rate 0.75 -> 0.5625)")
    for v in VARIANTS
])
def test_infra_errors_do_not_move_pass_rate(variant):
    fx = _fixture("metamorphic_infra.json")
    summarize = _summarize(variant)
    a, b = summarize(fx["a"]), summarize(fx["b"])
    for shape in a:
        assert b[shape]["pass_rate"] == pytest.approx(a[shape]["pass_rate"])


# Relation 2: the same trials listed twice keep every rate and double every total.
@pytest.mark.parametrize("variant", [
    _known_break(v, {"grader_a"}, "adds each claim's cost a second time, per claim not per trial")
    for v in VARIANTS
])
def test_duplicate_keeps_rates_doubles_totals(variant):
    fx = _fixture("metamorphic_duplicate.json")
    summarize = _summarize(variant)
    a, b = summarize(fx["a"]), summarize(fx["b"])
    for shape in a:
        for key in RATES:
            assert b[shape][key] == pytest.approx(a[shape][key]), key
        for key in TOTALS:
            assert b[shape][key] == pytest.approx(2 * a[shape][key]), key


# Relation 2b: pass^5 is a rate too, so duplication must not move it either.
# All three variants inherit lab8.metrics.summarize, which only counts a claim for pass^5
# when it has exactly one row per seed (`len(claim_rows) == len(seeds)`), so it drops to 0.
@pytest.mark.parametrize("variant", [
    _known_break(v, set(VARIANTS), "shared lab8.metrics needs exactly one row per seed (pass_5 0.667 -> 0.0)")
    for v in VARIANTS
])
def test_duplicate_keeps_pass5(variant):
    fx = _fixture("metamorphic_duplicate.json")
    summarize = _summarize(variant)
    a, b = summarize(fx["a"]), summarize(fx["b"])
    for shape in a:
        assert b[shape]["pass_5"] == pytest.approx(a[shape]["pass_5"])


# Relation 3 (business rule, not a grader): 2 days late is not eligible, 3 days is.
def test_delay_2_vs_3_flips_decision():
    fx = _fixture("metamorphic_claim_delay.json")
    two = quote(fx["a"]["order"], fx["policies"], as_of=fx["as_of"])
    three = quote(fx["b"]["order"], fx["policies"], as_of=fx["as_of"])
    # Hand-written from docs/business_rules.md: >= 3 days -> refund the shipping fee.
    assert fx["a"]["order"]["delay_days"] == 2 and fx["b"]["order"]["delay_days"] == 3
    assert two.amount_vnd == 0
    assert three.amount_vnd == fx["b"]["order"]["shipping_fee_vnd"] == 35000


# Relation 4 (new): shuffling the trial list must not change any number.
# The three relations above never reorder rows, so a grader that depends on which row
# it meets first for a claim slips past them on inputs where duplication is not involved.
@pytest.mark.parametrize("variant", [
    _known_break(v, {"grader_a"}, "keeps the cost of the first row it meets per claim, so order matters")
    for v in VARIANTS
])
def test_shuffled_trials_give_the_same_report(variant):
    trials = _fixture("metamorphic_infra.json")["b"]
    shuffled = list(reversed(trials))
    random.Random(7).shuffle(shuffled)
    summarize = _summarize(variant)
    a, b = summarize(trials), summarize(shuffled)
    for shape in a:
        for key in RATES + TOTALS:
            assert b[shape][key] == pytest.approx(a[shape][key]), key
