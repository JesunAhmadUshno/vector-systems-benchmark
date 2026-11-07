"""Pin the study's decision logic against the committed results.

generate_results.py turns results/cells.json into the hypothesis verdicts
and the C2 check. These tests run it on the committed file, so a change to a
verdict rule, or to the evidence, shows up here.
"""

import json
from pathlib import Path

import pytest

from vectorbench.generate_results import build, c2_check, verdicts, wilson

ROOT = Path(__file__).resolve().parents[1]
RESULTS = json.loads((ROOT / "results" / "cells.json").read_text())
ENV = json.loads((ROOT / "results" / "env.json").read_text())


def test_verdicts_match_committed_results():
    got = {v["id"]: v["verdict"] for v in verdicts(RESULTS)}
    assert got == {
        "H1": "Refuted",
        "H2": "Supported",
        "H3": "Supported",
        "H4": "Supported",
        "H5": "Supported",
        "H6": "Partially supported",
    }


def test_h2_discloses_its_cell_set():
    h2 = next(v for v in verdicts(RESULTS) if v["id"] == "H2")
    assert "Cells compared: 5" in h2["evidence"]
    assert "post-churn" in h2["evidence"]


def test_c2_check_agrees_one_band_up_and_disagrees_in_the_tight_cell():
    c2 = c2_check(RESULTS)
    assert round(c2["trap_tenant_t2"]["predicted"], 2) == 4.75
    assert round(c2["trap_tenant_t2"]["measured"], 2) == 4.86
    assert c2["trap_tenant_t2"]["agrees"] is True
    assert round(c2["trap_tenant_t5"]["predicted"], 2) == 0.42
    assert round(c2["trap_tenant_t5"]["measured"], 2) == 10.00
    assert c2["trap_tenant_t5"]["agrees"] is False


def test_wilson_known_answers():
    lo, hi = wilson(0.5, 100)
    assert lo == pytest.approx(0.4038, abs=1e-4)
    assert hi == pytest.approx(0.5962, abs=1e-4)
    lo, hi = wilson(0.0, 300)
    assert lo == pytest.approx(0.0, abs=1e-12)
    assert hi == pytest.approx(0.01264, abs=1e-5)


def test_shortfall_counts_are_whole_queries():
    for section in ("cells", "churn", "trap"):
        for e in RESULTS[section]:
            count = e["shortfall_rate"] * e["n_queries"]
            assert abs(count - round(count)) < 1e-6, (section, e["backend"], e["cell"])


def test_build_reports_sample_size_per_row():
    results_md, _ = build(RESULTS, ENV)
    assert "| qdrant | main | 1.000 | 100 x 2 |" in results_md
    assert "| faiss | main | 1.000 | 300 x 3 |" in results_md
    assert "Shortfall 95% CI" in results_md
