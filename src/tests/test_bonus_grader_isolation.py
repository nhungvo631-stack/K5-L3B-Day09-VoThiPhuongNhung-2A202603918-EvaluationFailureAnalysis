from __future__ import annotations

import pytest

from bonus.grader_audit import GRADERS, build_audit


@pytest.fixture(scope="module")
def audit():
    return build_audit()


def test_delay_threshold_flips_entitlement(audit):
    result = audit["claim_delay_business_rule"]
    assert result["holds"] is True
    assert result["quotes"]["a"]["amount_vnd"] == 0
    assert result["quotes"]["b"]["amount_vnd"] == 35000


@pytest.mark.parametrize("grader", GRADERS)
def test_infrastructure_error_metamorphic_relation(audit, grader):
    holds = audit["graders"][grader]["infrastructure_errors_excluded"]["holds"]
    assert holds is (grader != "grader_c")


@pytest.mark.parametrize("grader", GRADERS)
def test_duplicate_input_metamorphic_relation(audit, grader):
    result = audit["graders"][grader]["duplicate_input_scales_totals_only"]
    assert result["holds"] is False
    assert result["ratio_checks"]["pass_5"] is False
    if grader == "grader_a":
        assert result["ratio_checks"]["cost_per_success_vnd"] is False
        assert result["total_checks"]["total_simulated_cost_vnd"] is False
    else:
        assert result["ratio_checks"]["cost_per_success_vnd"] is True
        assert result["total_checks"]["total_simulated_cost_vnd"] is True


@pytest.mark.parametrize("grader", GRADERS)
def test_unrelated_shape_does_not_change_workflow_metrics(audit, grader):
    holds = audit["graders"][grader]["unrelated_shape_isolation"]["holds"]
    assert holds is True
