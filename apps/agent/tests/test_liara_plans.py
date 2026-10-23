"""Public planID extraction from GET /v1/me payloads."""

from app.api.liara import _public_project_plans


def test_public_project_plans_filters_cli_style() -> None:
    me = {
        "plans": {
            "projects": {
                "free": {
                    "available": True,
                    "region": "iran",
                    "RAM": {"amount": 0.5},
                    "CPU": {"amount": 0.5},
                    "volume": 1,
                },
                "g2-2x": {
                    "available": True,
                    "region": "iran",
                    "RAM": {"amount": 2},
                    "CPU": {"amount": 2},
                    "volume": 40,
                },
                "g2-eu": {
                    "available": True,
                    "region": "germany",
                    "RAM": {"amount": 1},
                    "CPU": {"amount": 1},
                    "volume": 10,
                },
                "legacy": {
                    "available": True,
                    "region": "iran",
                    "RAM": {"amount": 1},
                    "CPU": {"amount": 1},
                    "volume": 10,
                },
                "g2-off": {
                    "available": False,
                    "region": "iran",
                    "RAM": {"amount": 1},
                    "CPU": {"amount": 1},
                    "volume": 10,
                },
            }
        }
    }
    plans = _public_project_plans(me)
    ids = [p["id"] for p in plans]
    assert ids == ["free", "g2-2x"]
    assert plans[0]["label"] == "Free"
    assert "RAM" in str(plans[0]["hint"])
