from __future__ import annotations

import hashlib
import json
from pathlib import Path
import py_compile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    checks = {}

    # 1. Compile canonical package.
    failures = []
    for p in sorted((ROOT / "src" / "adrianic_memory").glob("*.py")):
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as exc:
            failures.append({"file": str(p.relative_to(ROOT)), "error": repr(exc)})
    checks["canonical_python_compiles"] = {"pass": not failures, "failures": failures}

    # 2. Original bundles remain valid ZIPs and hashes match manifest.
    manifest = json.loads((ROOT / "evidence" / "MANIFEST.json").read_text())
    bundle_failures = []
    for item in manifest:
        p = ROOT / "evidence" / "original_bundles" / item["file"]
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        with zipfile.ZipFile(p) as z:
            bad = z.testzip()
        if actual != item["sha256"] or bad is not None:
            bundle_failures.append({
                "file": item["file"],
                "hash_matches": actual == item["sha256"],
                "bad_member": bad,
            })
    checks["original_bundle_integrity"] = {"pass": not bundle_failures, "failures": bundle_failures}

    # 3. v3.15 original result still says what the reconstruction log says.
    v315root = ROOT / "evidence" / "extracted" / "adrianic_v3_15_optimal_seven_slots"
    results_path = next(v315root.rglob("results.json"))
    data = json.loads(results_path.read_text())
    fc = data["fault_coupled_search"]
    checks["v315_recorded_winner"] = {
        "pass": (
            fc["ranked"][0]["trio"] == "confidence+parityP+parityQ"
            and fc["heldout"][0]["trio"] == "confidence+parityP+parityQ"
            and abs(fc["heldout"][0]["heldout_score"] - 0.8600740846476203) < 1e-12
        ),
        "development": fc["ranked"][0],
        "heldout": fc["heldout"][0],
    }

    # 4. v5.0 retraction control must remain present and inverted.
    v50 = json.loads((ROOT / "logs" / "v50_oracle_control_source_exact.json").read_text())
    v50_ok = all(
        row["semantic_seed_mean"] < row["uniform_seed_mean"]
        and row["semantic_wins"] == 0
        for row in v50["summary"]
    )
    checks["v50_retraction_control"] = {"pass": v50_ok, "summary": v50["summary"]}

    # 5. Every results.json in recovered evidence parses.
    json_failures = []
    for p in sorted((ROOT / "evidence" / "extracted").rglob("results.json")):
        try:
            json.loads(p.read_text())
        except Exception as exc:
            json_failures.append({"file": str(p.relative_to(ROOT)), "error": repr(exc)})
    checks["result_json_parses"] = {"pass": not json_failures, "failures": json_failures}

    passed = all(v["pass"] for v in checks.values())
    out = {"pass": passed, "checks": checks}
    (ROOT / "logs" / "verification_report.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
