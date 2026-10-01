import json

from oi.contracts import ProductProfile, ProfileFact
from oi.profiles import ProfileStore

IPHONE = ProductProfile(known=True, summary="Ein Smartphone.", facts=[ProfileFact(label="Chip", value="A15 Bionic")],
                        released="September 2022", launch_price="999 €", trivia=[])


def test_a_product_is_found_by_its_name():
    store = ProfileStore(None)
    assert store.get("Apple iPhone 14", "de") is None
    store.put("Apple iPhone 14", "de", IPHONE)
    assert store.get("  apple  iPhone 14 ", "de") == IPHONE
    assert store.get("Apple iPhone 14", "en") is None  # an English profile is another profile


def test_profiles_survive_a_restart(tmp_path):
    path = tmp_path / "cache" / "profiles.json"
    ProfileStore(path).put("Apple iPhone 14", "de", IPHONE)
    assert ProfileStore(path).get("Apple iPhone 14", "de") == IPHONE


def test_a_broken_cache_file_is_ignored(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{ no json")
    store = ProfileStore(path)
    assert store.get("Apple iPhone 14", "de") is None
    store.put("Apple iPhone 14", "de", IPHONE)
    assert list(json.loads(path.read_text())) == ["de:apple iphone 14"]


def test_an_outdated_entry_is_skipped(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"de:old thing": {"summary": "no known field"},
                                "de:apple iphone 14": IPHONE.model_dump(mode="json")}))
    store = ProfileStore(path)
    assert store.get("old thing", "de") is None and store.get("Apple iPhone 14", "de") == IPHONE


def test_an_unwritable_cache_keeps_working_in_memory(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    store = ProfileStore(blocker / "profiles.json")  # its folder is a file: nothing can be written there
    store.put("Apple iPhone 14", "de", IPHONE)
    assert store.get("Apple iPhone 14", "de") == IPHONE
