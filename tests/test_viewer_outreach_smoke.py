from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_viewer_app_imports_with_outreach_workspace_present():
    app_path = ROOT / "viewer" / "app.py"
    source = app_path.read_text("utf-8")
    compile(source, "viewer/app.py", "exec")

    spec = importlib.util.spec_from_file_location("viewer_app", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert hasattr(module, "_render_outreach_workspace")
    assert "Outreach Workspace" in source
    assert "sendability_reason" in source
