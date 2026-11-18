"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math

from scipy.stats import bootstrap
import numpy as np

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    # TODO M2
    if len(human) != len(judge):
        raise ValueError("human and judge lengths differ")
    cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        h, j = h.upper(), j.upper()
        if h == POS and j == POS:
            cm["tp"] += 1
        elif h != POS and j == POS:
            cm["fp"] += 1
        elif h == POS and j != POS:
            cm["fn"] += 1
        else:
            cm["tn"] += 1
    return cm


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    # TODO M2: precision = tp/(tp+fp), recall = tp/(tp+fn); return 0.0 when the denominator is 0
    cm = confusion(human, judge)
    p = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    r = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return p, r


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    # TODO M2
    if len(human) != len(judge) or not human:
        raise ValueError("human and judge must be non-empty sequences of equal length")
    cm = confusion(human, judge)
    n = sum(cm.values())
    p_o = (cm["tp"] + cm["tn"]) / n
    p_fail_h = (cm["tp"] + cm["fn"]) / n
    p_fail_j = (cm["tp"] + cm["fp"]) / n
    p_pass_h = 1 - p_fail_h
    p_pass_j = 1 - p_fail_j
    p_e = p_fail_h * p_fail_j + p_pass_h * p_pass_j
    if p_e == 1:
        raise ValueError("kappa undefined: judge and human agreement is degenerate")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    # TODO M2: (p_obs + spec - 1) / (sens + spec - 1)
    denominator = sensitivity + specificity - 1
    if denominator == 0:
        return 0.0
    corrected = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    # TODO M4
    if len(a) != len(b):
        raise ValueError("paired samples have different lengths")
    if not a:
        raise ValueError("paired samples must not be empty")
    av = np.asarray(a, dtype=float)
    bv = np.asarray(b, dtype=float)
    if np.array_equal(av, bv):
        return 0.0, 0.0, 0.0
    def statistic(x, y):
        return float(np.mean(x) - np.mean(y))
    res = bootstrap((av, bv), statistic, n_resamples=n_resamples,
                    method="percentile", paired=True,
                    confidence_level=confidence,
                    random_state=np.random.default_rng(rng))
    lo, hi = (float(res.confidence_interval.low), float(res.confidence_interval.high))
    return statistic(av, bv), lo, hi


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    # TODO M6
    import math
    if k < 1 or k > n or c < 0 or c > n:
        raise ValueError("invalid pass@k arguments")
    if k > n - c:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    # TODO M6
    import math
    if k < 1 or k > n or c < 0 or c > n:
        raise ValueError("invalid pass^k arguments")
    if k > c:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)
