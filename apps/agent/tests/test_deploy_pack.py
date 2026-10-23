"""Archive packing for Nest/Liara PaaS quirks."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from app.services.deploy import pack_app_source_archive, _verify_url_candidates, verify_deploy


def test_pack_rewrites_nest_build_when_dist_present(tmp_path: Path) -> None:
    root = tmp_path / "api"
    root.mkdir()
    (root / "nest-cli.json").write_text("{}", encoding="utf-8")
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "scripts": {
                    "build": "nest build",
                    "start": "node dist/main.js",
                    "prisma:generate": "prisma generate",
                },
                "dependencies": {"@prisma/client": "6.5.0"},
                "devDependencies": {"prisma": "6.5.0"},
            }
        ),
        encoding="utf-8",
    )
    (root / "prisma").mkdir()
    (root / "prisma" / "schema.prisma").write_text(
        'generator client { provider = "prisma-client-js" }\n',
        encoding="utf-8",
    )
    (root / "prisma" / "migrations").mkdir()
    (root / "dist").mkdir()
    (root / "dist" / "main.js").write_text(
        "await app.listen(config.PORT);\n", encoding="utf-8"
    )

    archive = pack_app_source_archive(root)
    with tarfile.open(archive, "r:gz") as tar:
        pkg = json.loads(
            (tar.extractfile("./package.json") or tar.extractfile("package.json")).read()
        )
        main = (
            tar.extractfile("./dist/main.js") or tar.extractfile("dist/main.js")
        ).read().decode("utf-8")

    assert pkg["scripts"]["build"] == "prisma generate"
    assert "prisma migrate deploy" in pkg["scripts"]["start"]
    assert "prisma" in pkg["dependencies"]
    assert '0.0.0.0' in main


def test_verify_url_candidates_include_nest_health() -> None:
    urls = _verify_url_candidates("https://mail-inbox.liara.run")
    assert urls[0] == "https://mail-inbox.liara.run"
    assert "https://mail-inbox.liara.run/api/health" in urls


def test_verify_rejects_root_stub_even_if_health_ok() -> None:
    calls: list[str] = []

    def http_get(url: str) -> tuple[int, str]:
        calls.append(url)
        if url.rstrip("/").endswith("health"):
            return 200, '{"status":"ok"}'
        return 200, "ok 1234567890123"

    result = verify_deploy(
        provider_ids={
            "project_name": "mail-inbox",
            "releaseID": "rel-1",
            "app_url": "https://mail-inbox.liara.run",
        },
        http_get=http_get,
        poll_attempts=1,
        poll_delay_sec=0,
        require_http=True,
    )
    assert result["http_stub_detected"] is True
    assert result["http_ok"] is False
    assert result["ok"] is False
    assert calls[0] == "https://mail-inbox.liara.run"
