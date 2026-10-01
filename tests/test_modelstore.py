from oi.contracts import MeasureSheet, ModelManifest, ModelPart
from oi.modelstore import ModelStore, slug


def manifest(model: str = "Apple iPhone 14", parts: int = 2) -> ModelManifest:
    return ModelManifest(
        model=model, slug=slug(model), size_mm=(71.5, 146.7, 7.8), sheet=MeasureSheet.estimated(), drawing_pages=[],
        notes="", verdict="good", rounds=1, cost_usd=0.9, created="2026-10-01T22:00:00",
        parts=[ModelPart(name=f"Teil {i}", color="#9fc4e8", file=f"part-{i:02d}.stl", min_mm=(0, 0, 0),
                         max_mm=(1, 1, 1), triangles=12) for i in range(1, parts + 1)])


def test_slug():
    assert slug("Apple iPhone 14") == "apple-iphone-14"
    assert slug("Sony DualShock 3 (CECHZC2E)") == "sony-dualshock-3-cechzc2e"
    assert slug("  Ünïcode / Stuff  ") == "n-code-stuff"
    assert slug("") == slug("!!!") == "model"
    assert len(slug("x" * 200)) == 80


def test_put_get_and_files_on_disk(tmp_path):
    store = ModelStore(tmp_path)
    store.put(manifest(), [b"stl one", b"stl two"], "cube(1);")
    folder = tmp_path / "apple-iphone-14"
    assert sorted(p.name for p in folder.iterdir()) == ["manifest.json", "model.scad", "part-01.stl", "part-02.stl"]
    again = ModelStore(tmp_path)  # a restart reads it from disk
    assert again.get("Apple iPhone 14") == manifest()
    assert again.get(" apple  iPhone 14 ") == manifest()  # the same model in other spelling
    assert again.file("apple-iphone-14", "part-02.stl") == b"stl two"
    assert again.file("apple-iphone-14", "model.scad") == b"cube(1);"
    assert again.get("Apple iPhone 15") is None


def test_get_refuses_a_manifest_of_another_model(tmp_path):
    store = ModelStore(tmp_path)
    store.put(manifest("Apple iPhone 14"), [b"a", b"b"], "")
    assert store.get("Apple-iPhone 14") is None  # same slug, but another model name: never served under it
    (tmp_path / "apple-iphone-14" / "part-02.stl").unlink()
    assert ModelStore(tmp_path).get("Apple iPhone 14") is None  # a part file is missing


def test_file_serves_only_listed_files(tmp_path):
    store = ModelStore(tmp_path)
    store.put(manifest(), [b"a", b"b"], "code")
    for slug_, name in [("apple-iphone-14", "../manifest.json"), ("apple-iphone-14", "manifest.json"),
                        ("apple-iphone-14", "part-99.stl"), ("apple-iphone-14", "x/../model.scad"),
                        ("../apple-iphone-14", "part-01.stl"), ("unknown", "part-01.stl")]:
        assert store.file(slug_, name) is None, (slug_, name)


def test_memory_store():
    store = ModelStore(None)
    assert store.get("Apple iPhone 14") is None
    store.put(manifest(), [b"a", b"b"], "code")
    assert store.get("Apple iPhone 14") == manifest()
    assert store.file("apple-iphone-14", "part-01.stl") == b"a"
    assert ModelStore(None).get("Apple iPhone 14") is None  # memory only: nothing shared between stores
