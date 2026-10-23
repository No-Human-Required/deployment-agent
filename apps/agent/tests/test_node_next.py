"""Node/Next readiness adapter — file-backed findings."""

from __future__ import annotations

from pathlib import Path

from app.adapters.node_next import assess_node_next

FIXTURE_MISSING = (
    Path(__file__).resolve().parent / "fixtures" / "node_app_missing"
)


def test_fixture_reports_missing_port_and_start() -> None:
    result = assess_node_next(FIXTURE_MISSING)
    assert result.ready is False
    assert result.platform == "next"
    codes = {f.code for f in result.findings}
    assert "missing_start_script" in codes
    assert "missing_port" in codes
    for finding in result.findings:
        if finding.code in ("missing_start_script", "missing_port"):
            assert finding.evidence_paths
            assert any("package.json" in p for p in finding.evidence_paths)


def test_ready_when_port_and_start_present(tmp_path: Path) -> None:
    pkg = tmp_path / "package.json"
    pkg.write_text(
        """
        {
          "name": "ok-app",
          "scripts": { "start": "node server.js -p 3000" },
          "dependencies": { "express": "4.18.0" }
        }
        """.strip(),
        encoding="utf-8",
    )
    result = assess_node_next(tmp_path)
    assert result.ready is True
    assert result.platform == "nodejs"
    assert result.detected_port == 3000
    assert result.start_script is not None
