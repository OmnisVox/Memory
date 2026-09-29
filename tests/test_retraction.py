import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v50_retraction_is_explicit():
    text = (ROOT / "docs" / "RETRACTION_LEDGER.md").read_text()
    assert "R-001" in text
    assert "EMPIRICAL CLAIM RETRACTED" in text
    assert "ARCHITECTURE REMAINS OPEN" in text


def test_v50_oracle_control_inverts_semantic_prior():
    data = json.loads((ROOT / "logs" / "v50_oracle_control_source_exact.json").read_text())
    assert len(data["summary"]) == 3
    for row in data["summary"]:
        assert row["semantic_seed_mean"] < row["uniform_seed_mean"]
        assert row["semantic_wins"] == 0
    clean = next(r for r in data["summary"] if r["noise"] == 0.0)
    assert abs(clean["semantic_seed_mean"] - 0.9663007531030035) < 1e-12
    assert abs(clean["uniform_seed_mean"] - 1.0) < 1e-12
    assert abs(clean["exact_two_sided_p_when_all_nonzero_same_sign"] - 0.03125) < 1e-12


def test_v50_surviving_coverage_measurements_present():
    import csv
    p = ROOT / "evidence" / "extracted" / "adrianic_v5_0_semantic_governance" / "v50_8seed_pooled_metrics_VERIFIED.csv"
    with p.open(newline="") as f:
        rows = list(csv.DictReader(f))
    clean = next(r for r in rows if float(r["noise"]) == 0.0)
    assert abs(float(clean["semantic_top1_accuracy"]) - 0.2609375) < 1e-12
    assert abs(float(clean["semantic_topk_coverage"]) - 0.7671875) < 1e-12
