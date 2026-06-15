from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "packages" / "feiyue-web"
DOC = ROOT / "docs" / "feiyue-frontend-hermes-embedding.md"


def test_frontend_architecture_doc_defines_hermes_bridge_boundary() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "Feiyue Backend + Hermes Bridge sidecar" in text
    assert "The browser is an operator surface, not an agent runtime." in text
    assert "no browser-side secrets" in text
    assert "RoutingApplyGate" in text
    assert "exact approval" in text
    assert "recursive evaluation surface" in text
    assert "feiyue-frontend-dogfood-real-task.md" in text


def test_frontend_dogfood_plan_treats_frontend_as_real_feiyue_task() -> None:
    text = (ROOT / "docs" / "plans" / "feiyue-frontend-dogfood-real-task.md").read_text(encoding="utf-8")

    assert "Feiyue plans Feiyue frontend" in text
    assert "Hermes-backed worker implements bounded frontend slices" in text
    assert "evidence updates capability history" in text
    assert '"provider_call_count": 0' in text
    assert "global_hermes_config_mutated" in text
    assert "production_mutated" in text


def test_frontend_scaffold_is_read_only_by_default() -> None:
    html = (WEB / "src" / "index.html").read_text(encoding="utf-8")
    js = (WEB / "src" / "app.js").read_text(encoding="utf-8")
    css = (WEB / "src" / "styles.css").read_text(encoding="utf-8")
    combined = "\n".join([html, js, css]).lower()

    assert "feiyue operator console" in html.lower()
    assert "hermes agent console" in html.lower()
    assert "data-action=\"create-hermes-session-draft\"" in html
    assert "start-hermes-session-draft" not in html
    assert "disabled data-action=\"apply-routing-proposal\"" in html
    assert "<form" not in combined
    assert "method=\"post" not in combined

    assert "localstorage" not in combined
    assert "sessionstorage" not in combined


def test_frontend_scaffold_uses_dark_institutional_palette() -> None:
    css = (WEB / "src" / "styles.css").read_text(encoding="utf-8")

    assert "--bg: #0b0f14" in css
    assert "--panel: #111827" in css
    assert "--ink: #e5e7eb" in css
    assert "--accent: #2dd4bf" in css
