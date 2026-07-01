import os, sys, pathlib, json

os.environ["STORAGE_MODE"] = "json"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))


def test_pipeline_scripts_exist():
    base = pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"
    scripts = [
        "scripts/prospecting/pipeline_unified.py",
        "scripts/prospecting/extract.py",
        "scripts/prospecting/neon_db.py",
        "scripts/prospecting/neon_schema.sql",
    ]
    for s in scripts:
        assert (base / s).exists(), f"Missing: {s}"


def test_pipeline_imports():
    sys.path.insert(0, str(
        pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting" / "scripts" / "prospecting"
    ))
    import pipeline_unified
    assert hasattr(pipeline_unified, "main")


def test_categories_json_exists():
    path = pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting" / "references" / "categories.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert len(data) > 0


def test_pipeline_shopify_script_exists():
    path = pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting" / "shopify-ops" / "shopify_ops.py"
    assert path.exists()


def test_neon_schema_has_tenant_id():
    path = pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting" / "scripts" / "prospecting" / "neon_schema.sql"
    schema = path.read_text(encoding="utf-8")
    assert "tenant_id" in schema
