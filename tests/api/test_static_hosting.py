from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from apps.api.app.settings import Settings
from data.domain import RuntimeMode


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        runtime_mode=RuntimeMode.FALLBACK,
        database_url=f"sqlite:///{tmp_path / 'static.db'}",
    )


def test_spa_is_optional_when_distribution_is_absent(tmp_path):
    with TestClient(
        create_app(_settings(tmp_path), static_directory=tmp_path / "missing")
    ) as client:
        assert client.get("/").status_code == 404
        assert client.get("/health").status_code == 200
        assert client.get("/api/runtime").status_code == 200


def test_spa_fallback_serves_navigation_without_shadowing_api(tmp_path):
    distribution = tmp_path / "dist"
    (distribution / "assets").mkdir(parents=True)
    (distribution / "index.html").write_text("<main>Supply Response</main>")
    (distribution / "assets" / "app.js").write_text("console.log('built')")

    with TestClient(
        create_app(_settings(tmp_path), static_directory=distribution)
    ) as client:
        assert client.get("/").text == "<main>Supply Response</main>"
        assert client.get("/cases/RL-001").text == "<main>Supply Response</main>"
        assert client.get("/assets/app.js").text == "console.log('built')"
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/api/runtime").status_code == 200
        assert client.get("/api").status_code == 404
        assert client.get("/api/not-a-real-route").status_code == 404
