from pathlib import Path
import hashlib, json, zipfile, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "MANIFEST.json").read_text())

errors = []
for rel, info in manifest["files"].items():
    p = ROOT / rel
    if not p.exists():
        errors.append(f"missing: {rel}")
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != info["sha256"]:
        errors.append(f"hash mismatch: {rel}")

# Validate notebooks parse as JSON.
for p in ROOT.rglob("*.ipynb"):
    try:
        json.loads(p.read_text())
    except Exception as e:
        errors.append(f"bad notebook {p.relative_to(ROOT)}: {e}")

# Run isolated relational smoke test.
smoke = ROOT / "relational_sidecar" / "smoke_test.py"
if smoke.exists():
    r = subprocess.run([sys.executable, str(smoke)], cwd=smoke.parent,
                       capture_output=True, text=True)
    if r.returncode != 0 or "PASS" not in r.stdout:
        errors.append("relational smoke test failed: " + r.stdout + r.stderr)

if errors:
    print("FAIL")
    print("\n".join(errors))
    raise SystemExit(1)
print("PASS")
print(f"Verified {len(manifest['files'])} archived files.")
