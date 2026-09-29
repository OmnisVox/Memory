from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def _nb_text(name):
    p = ROOT / "evidence" / "semantic_reasoning_lineage" / name
    nb = json.loads(p.read_text())
    return "\n".join("".join(c.get("source", [])) for c in nb["cells"])


def test_v4_retraction_boundary_is_explicit():
    text = (ROOT / "docs" / "V4_EVIDENCE_BOUNDARIES.md").read_text()
    assert "R-001 starts at v5.0" in text
    assert "Family A" in text and "Family B" in text
    assert "local smoke/proxy evidence" in text


def test_v40_corpus_evidence_is_nonsemantic():
    text = _nb_text("Adrianic_v4_0_Semantic_Bootstrap_Transfer_Lab_COLAB_GPU_SAFE.ipynb")
    assert "recurrence" in text and "cross_context" in text and "predictability" in text
    assert "Correlated signals discount each other; no semantic labels are used." in text


def test_v44_multiconsequence_channels_present():
    text = _nb_text("Adrianic_v4_4_MultiConsequence_AdaptiveBinding_COLAB_SAFE.ipynb")
    for name in ("gain_early_mid", "gain_mid_final", "future_support", "context_gain"):
        assert name in text


def test_v49_is_binary_opaque_randomized_world_not_v50_hash_helper():
    text = _nb_text("Adrianic_v4_9_SymmetricDecoy_ConsequenceArbitration_COLAB_SAFE.ipynb")
    assert "def opaque_token" in text
    assert "class ShuffledTrust" in text
    assert "class FrozenTrust" in text
    assert "class CoherenceOnlyTrust" in text
    assert "def forecast_code" not in text
