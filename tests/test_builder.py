import io

import pytest
from PIL import Image

from oi.builder import ModelBuilder
from oi.config import Settings
from oi.contracts import DrawingRef, MeasureSheet, PhotoRef, Source
from oi.identify import IdentifyError
from oi.measure import ViewBoxes
from oi.modelcalls import CadPart, CadProgram, CheckAnswer, FakeModelCalls
from oi.modelstore import ModelStore
from oi.scad import FakeCompiler
from oi.telemetry import SessionBudget

MODEL = "Apple iPhone 14"
TWO_PARTS = CadProgram(shared="w = 71.5;", parts=[CadPart("Gehäuse", "#9fc4e8", "cube(w);"),
                                                  CadPart("Linse", "#111111", "cyl(d=13, h=2);")], notes="")


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), (250, 250, 250)).save(buffer, "PNG")
    return buffer.getvalue()


async def fetch_png(url, allowed):
    assert url in allowed
    return png(), "image/png"


def fake_render(parts, size=512):
    assert parts and all(colour.startswith("#") for _, colour in parts)
    return [png()] * 4


class Log:
    def __init__(self) -> None:
        self.records = []

    def write(self, record) -> None:
        self.records.append(record)


def builder(calls=None, compiler=None, settings=None, store=None, log=None, budget=None):
    events = []
    built = ModelBuilder(settings or Settings(), calls or FakeModelCalls(), compiler or FakeCompiler(),
                         store if store is not None else ModelStore(None), budget or SessionBudget(), log,
                         fetch=fetch_png, render=fake_render)

    async def listen(model, status, round_, manifest):
        events.append((model, status, round_, manifest))

    built.listen(listen)
    return built, events


def statuses(events, model=MODEL):
    return [(s, r) if s == "checking" else s for m, s, r, _ in events if m == model]


async def build(built, model=MODEL):
    await built.request(model, "Smartphone", b"\xff\xd8crop")
    await built.wait_idle()


async def test_a_good_first_check_ends_early_with_the_statuses_in_order():
    calls = FakeModelCalls()
    built, events = builder(calls)
    await build(built)
    assert statuses(events) == ["queued", "researching", "modeling", "building", ("checking", 1), "ready"]
    manifest = events[-1][3]
    assert manifest is not None and manifest.verdict == "good" and manifest.rounds == 1
    assert [p.file for p in manifest.parts] == ["part-01.stl"] and manifest.size_mm == (10.0, 10.0, 10.0)
    assert built.state(MODEL) == ("ready", 1, manifest)
    assert len(calls.check_requests) == 1 and calls.cad_requests[0].jpeg == b"\xff\xd8crop"
    assert len(calls.check_requests[0].renders) == 4


async def test_unkept_model_is_rebuilt_once_per_run():
    store = ModelStore(None)
    first, _ = builder(store=store)
    await build(first)
    calls = FakeModelCalls()
    again, events = builder(calls, store=store)  # the next server run
    assert again.state(MODEL) is None  # stored, but not kept: not shown
    await build(again)
    await build(again)  # picked up again in the same run: no second build
    assert len(calls.research_requests) == 1 and statuses(events)[-1] == "ready"
    assert again.state(MODEL) == ("ready", 1, events[-1][3])


async def test_kept_model_is_never_rebuilt():
    store = ModelStore(None)
    first, _ = builder(store=store)
    await build(first)
    store.set_kept(MODEL, True)
    calls = FakeModelCalls()
    again, events = builder(calls, store=store)
    await build(again)
    assert calls.research_requests == [] and events == []
    assert again.state(MODEL)[0] == "ready" and again.state(MODEL)[2].kept


async def test_drawing_step_only_with_a_candidate():
    sheet = MeasureSheet(size_mm=(71.5, 146.7, 7.8), size_source=0, measures=[], features=[],
                         sources=[Source(title="Apple", url="https://www.apple.com/a")],
                         drawing=DrawingRef(url="https://developer.apple.com/d.png", find="iPhone 14"))
    calls = FakeModelCalls(research=sheet)
    built, events = builder(calls)
    await build(built)
    assert "drawing" in statuses(events)
    assert [m for _, m in calls.cad_requests[0].drawings] == ["image/png"]
    assert events[-1][3].size_mm == (71.5, 146.7, 7.8)  # the researched size, not the cube's
    plain, plain_events = builder()
    await build(plain)
    assert "drawing" not in statuses(plain_events)


async def test_compile_errors_go_to_the_next_check_and_broken_parts_drop_out():
    try_again = [CheckAnswer("fix", ["Linse kaputt"], None, [CadPart("Linse", "#111111", f"cyl(d={d}, h=2);")], [])
                 for d in (12, 11)]
    calls = FakeModelCalls(cad=TWO_PARTS, checks=try_again)
    compiler = FakeCompiler(broken={"Linse"})
    built, events = builder(calls, compiler)
    await build(built)
    first = calls.check_requests[0]
    assert first.errors == {"Linse": ["ERROR: Parser error"]}
    assert compiler.calls == [["Gehäuse", "Linse"], ["Linse"], ["Linse"]]  # only the changed part again
    manifest = events[-1][3]
    assert [p.name for p in manifest.parts] == ["Gehäuse"] and "Linse" in manifest.notes
    assert (manifest.verdict, manifest.rounds) == ("fix", 2)


async def test_nothing_compiles_means_failed():
    built, events = builder(FakeModelCalls(), FakeCompiler(broken={"Gehäuse"}))
    await build(built)
    assert statuses(events)[-1] == "failed" and built.state(MODEL)[0] == "failed"


async def test_research_error_means_estimated_measures():
    built, events = builder(FakeModelCalls(research=IdentifyError("api")))
    await build(built)
    assert events[-1][1] == "ready" and events[-1][3].sheet == MeasureSheet.estimated()


async def test_research_over_the_cap_stops_before_cad():
    budget = SessionBudget()
    calls = FakeModelCalls(costs=(1.7, 0.0, 0.0, 0.0))
    built, events = builder(calls, budget=budget)
    await build(built)
    assert statuses(events)[-1] == "failed" and calls.cad_requests == []
    assert budget.cost_usd == pytest.approx(1.7) and budget.calls == 1


async def test_budget_ends_checks_early():
    fix = CheckAnswer("fix", ["zu dick"], None, [CadPart("Gehäuse", "#9fc4e8", "cube(9, center=true);")], [])
    calls = FakeModelCalls(costs=(0.5, 0.0, 0.5, 0.4), checks=[fix, fix])
    built, events = builder(calls)
    await build(built)
    manifest = events[-1][3]
    assert len(calls.check_requests) == 1 and "Budget erreicht." in manifest.notes
    assert manifest.cost_usd == pytest.approx(1.4) and manifest.verdict == "fix"


async def test_one_job_at_a_time_and_queue_order():
    built, events = builder()
    await built.request(MODEL, "Smartphone", None)
    await built.request("Sony DualShock 3", "Gamecontroller", None)
    await built.request(MODEL, "Smartphone", None)  # already queued: nothing new
    await built.wait_idle()
    order = [(m, s) for m, s, _, _ in events]
    assert order.index((MODEL, "ready")) < order.index(("Sony DualShock 3", "researching"))
    assert order.count((MODEL, "queued")) == 1


async def test_session_limit_after_five_new_models():
    built, events = builder(settings=Settings(max_models_session=1))
    await build(built)
    await build(built, "Sony DualShock 3")
    assert statuses(events, "Sony DualShock 3") == ["limit"]
    assert built.state("Sony DualShock 3")[0] == "limit"
    await build(built)  # the cached one is still there
    assert built.state(MODEL)[0] == "ready"


async def test_rebuild_only_after_failure():
    calls = FakeModelCalls(cad=IdentifyError("timeout"))
    built, events = builder(calls)
    await build(built)
    assert built.state(MODEL)[0] == "failed"
    calls.cad = TWO_PARTS
    await built.rebuild(MODEL)
    await built.wait_idle()
    assert built.state(MODEL)[0] == "ready" and len(calls.cad_requests) == 2
    await built.rebuild(MODEL)  # ready: nothing happens
    await built.wait_idle()
    assert len(calls.cad_requests) == 2


async def test_calls_count_in_the_session_budget_and_the_log():
    log, budget = Log(), SessionBudget()
    fix = CheckAnswer("fix", [], None, [], [])
    built, _ = builder(FakeModelCalls(checks=[fix], costs=(0.1, 0.0, 0.2, 0.05)), log=log, budget=budget)
    await build(built)
    texts = [r.request_text for r in log.records]
    assert texts == [f"model research: {MODEL}", f"model cad: {MODEL}", f"model check 1: {MODEL}",
                     f"model check 2: {MODEL}"]
    assert all(r.track_id == -2 for r in log.records) and budget.calls == 4
    assert budget.cost_usd == pytest.approx(0.1 + 0.2 + 0.05 + 0.05)


# --- sub-project 7: measuring ---------------------------------------------------------------------------------------

PAD = "Sony DualShock 3"
PHOTO_SHEET = MeasureSheet(size_mm=(160.0, 97.0, 55.0), size_source=0, measures=[], features=[],
                           sources=[Source(title="Dimensions", url="https://www.dimensions.com/e/ds3")], drawing=None,
                           photos=[PhotoRef(url="https://www.dimensions.com/front.png", view="front"),
                                   PhotoRef(url="https://www.dimensions.com/top.png", view="top")])
# the photos are 40 × 20 px (fetch_png): this box is 32 × 19.4 px, 5 mm per pixel both ways
FRONT = ViewBoxes(picture=1, view="front", object=(0.1, 0.0, 0.9, 0.97),
                  parts=[("Gehäuse", (0.1, 0.0, 0.9, 0.97)), ("Dreieck-Taste", (0.7, 0.2, 0.75, 0.3))])


async def test_measuring_step_feeds_cad_and_checks():
    calls = FakeModelCalls(research=PHOTO_SHEET, measure=[FRONT])
    built, events = builder(calls)
    await build(built, PAD)
    assert statuses(events, PAD) == ["queued", "researching", "drawing", "measuring", "modeling", "building",
                                     ("checking", 1), "ready"]
    assert [label for _, label in calls.measure_requests[0].pictures] == ["photo, front", "photo, top"]
    cad = calls.cad_requests[0]
    assert "Dreieck-Taste: x 40.0…50.0, y 18.5…28.5 mm (1 view)" in cad.part_map
    assert [view for _, view in cad.photos] == ["front", "top"]
    off = calls.check_requests[0].deviations  # the fake CAD is one 10 mm cube
    assert off[0].startswith("Dreieck-Taste: missing") and off[1].startswith("Gehäuse: x model -5.0…5.0")
    manifest = events[-1][3]
    assert [p.name for p in manifest.part_map] == ["Gehäuse", "Dreieck-Taste"]
    assert "Noch 3 Abweichungen über der Toleranz." in manifest.notes


async def test_no_pictures_or_no_size_means_no_measuring():
    calls = FakeModelCalls(measure=[FRONT])  # no research: no drawing, no photos
    built, events = builder(calls)
    await build(built)
    assert "measuring" not in statuses(events) and calls.measure_requests == []
    calls = FakeModelCalls(research=PHOTO_SHEET.model_copy(update={"size_mm": None}), measure=[FRONT])
    built, events = builder(calls)
    await build(built, PAD)
    assert "measuring" not in statuses(events, PAD) and calls.measure_requests == []
    assert calls.cad_requests[0].part_map == "" and len(calls.cad_requests[0].photos) == 2


async def test_measure_error_builds_without_map():
    calls = FakeModelCalls(research=PHOTO_SHEET, measure=IdentifyError("api"))
    built, events = builder(calls)
    await build(built, PAD)
    assert events[-1][1] == "ready" and events[-1][3].part_map == []
    assert calls.cad_requests[0].part_map == "" and calls.check_requests[0].deviations == []


async def test_measure_respects_the_reserve():
    calls = FakeModelCalls(research=PHOTO_SHEET, measure=[FRONT], costs=(1.2, 0.0, 0.0, 0.0))
    built, events = builder(calls)
    await build(built, PAD)
    assert calls.measure_requests == [] and "measuring" not in statuses(events, PAD)
    assert statuses(events, PAD)[-1] == "failed"  # 1.20 + 0.45 for the CAD is over 1.60, as before
    calls = FakeModelCalls(research=PHOTO_SHEET, measure=[FRONT], costs=(0.95, 0.0, 0.0, 0.0))
    built, events = builder(calls)
    await build(built, PAD)
    assert calls.measure_requests == []  # 0.95 + 0.25 + 0.45 > 1.60: the CAD could not follow the map
    assert calls.cad_requests and statuses(events, PAD)[-1] == "ready"


async def test_kept_matches_other_names_once():
    store = ModelStore(None)
    first, _ = builder(store=store)
    await build(first, PAD)
    store.set_kept(PAD, True)
    calls = FakeModelCalls(same=PAD)
    again, _ = builder(calls, store=store)
    assert (await again.kept("Sony PlayStation 3 DualShock 3")).model == PAD
    assert (await again.kept("Sony PlayStation 3 DualShock 3")).model == PAD  # asked once per name and run
    assert len(calls.same_requests) == 1 and calls.same_requests[0].candidates == [PAD]
    assert (await again.kept(PAD)).model == PAD and len(calls.same_requests) == 1  # its own name: no call
    store.set_kept(PAD, False)
    assert await again.kept("Sony PlayStation 3 DualShock 3") is None  # no longer kept
    lonely = FakeModelCalls(same=PAD)
    alone, _ = builder(lonely)  # nothing is kept
    assert await alone.kept("Sony PlayStation 3 DualShock 3") is None and lonely.same_requests == []


async def test_keep_reaches_every_listener():
    store = ModelStore(None)
    built, events = builder(store=store)
    await build(built)
    await built.keep(MODEL, True)
    assert events[-1][1:3] == ("ready", 1) and events[-1][3].kept and store.get(MODEL).kept
    await built.keep("Unbekannt", True)  # nothing stored under that name: nothing happens
    assert events[-1][3].model == MODEL
