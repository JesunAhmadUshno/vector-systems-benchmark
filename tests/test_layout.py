"""Portfolio standard checks: the lock holds, the required files exist, no grade is public."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# SHA-256 of each file as committed in 838e6da (tag proposal-v1), before any experiment code.
LOCKED = {
    "SPEC.md": "d3f3c2d19b8412614128909fe91ac26ee220aa5722e3ea3e1a0ce2ca98fb8f08",
    "HYPOTHESES.md": "047582e868d56302e5d45075d5b8a3855d27796a9c54bcde4736da4adead7eda",
}
PUBLIC = ["README.md", "REPORT.md", "AUDIT.md", "RESULTS.md", "DECISIONS.md", "METHODS.md",
          "RESEARCH.md", "CHANGELOG.md", "site/src/App.jsx"]


def test_locked_proposal_is_unchanged():
    for name, want in LOCKED.items():
        got = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert got == want, f"{name} changed after its lock; record an amendment in DECISIONS.md instead"


def test_required_files_exist():
    need = ["README.md", "SPEC.md", "HYPOTHESES.md", "REPORT.md", "RESULTS.md", "DECISIONS.md",
            "METHODS.md", "CHANGELOG.md", "CITATION.cff", "SECURITY.md", "LICENSE",
            "results/cells.json", "results/env.json", "results_pg/cells.json", "results_qdrant/cells.json"]
    missing = [p for p in need if not (ROOT / p).exists()]
    assert not missing, "missing: " + ", ".join(missing)


def test_no_public_grade():
    pat = re.compile(r"of 10,000|/ ?10,?000|Grade:|grade on the house|Minus \d", re.I)
    for name in PUBLIC:
        hit = pat.search((ROOT / name).read_text())
        assert not hit, f"{name} carries a grade ({hit.group(0)!r}); grades are internal"


def test_report_headline_table_is_the_generated_one():
    table = (ROOT / "results" / "readme_table.md").read_text().strip()
    assert table in (ROOT / "REPORT.md").read_text(), "REPORT.md headline table differs from results/readme_table.md"


def test_readme_abstract_and_lifecycle():
    text = (ROOT / "README.md").read_text()
    for tag in ("**Question.**", "**Headline.**", "**Field.**", "**Job family.**", "**Verdict.**", "## Lifecycle"):
        assert tag in text, "README is missing " + tag
    stages = re.findall(r"^- (\w+): (DONE|PARTIAL|OPEN)", text, re.M)
    assert [s for s, _ in stages] == ["Question", "Proposal", "Baseline", "Build", "Evaluate", "Report", "Review", "Release"]
