from oi.belief import Belief
from oi.contracts import Level
from tests.helpers import cand, obs

I14, I13, I15 = cand("Apple", "iPhone 14", ev=("Apple-Logo",)), cand("Apple", "iPhone 13"), cand("Apple", "iPhone 15")


def test_no_observation():
    state = Belief("de").snapshot(0)
    assert state.level is None and state.line == "" and not state.final


def test_single_view_is_at_most_likely():
    b = Belief("de")
    b.add(obs(I14, I13), 1, 1.0)
    state = b.snapshot(1)
    assert state.level == Level.LIKELY
    assert state.line == "Das ist wahrscheinlich Apple iPhone 14."
    assert [c.name for c in state.candidates] == ["Apple iPhone 14", "Apple iPhone 13"]
    assert state.candidates[0].share == 2 / 3 and state.evidence == ["Apple-Logo"] and state.calls_used == 1


def test_two_agreeing_views_make_certain():
    b = Belief("de")
    b.add(obs(I14, I13), 1, 1.0)
    b.add(obs(I14, I13), 2, 1.0)
    state = b.snapshot(2)
    assert (state.level, state.line, state.final) == (Level.CERTAIN, "Das ist Apple iPhone 14.", True)
    assert b.is_final


def test_same_view_twice_is_not_two_views():
    b = Belief("de")
    b.add(obs(I14, I13), 1, 1.0)
    b.add(obs(I14, I13), 1, 1.0)
    assert b.snapshot(2).level == Level.LIKELY


def test_close_race_is_unsure_with_view_request():
    b = Belief("de")
    b.add(obs(I14, I13), 1, 1.0)
    b.add(obs(I13, I14, view="die Unterseite", reason="Lightning oder USB-C"), 2, 1.0)
    state = b.snapshot(2)
    assert state.level == Level.UNSURE and not state.final
    assert state.view_request.view == "die Unterseite"
    assert state.line == "Apple iPhone 14 oder Apple iPhone 13? Zeig mir bitte die Unterseite."


def test_iphone_example_ends_indistinguishable():
    b = Belief("de")
    b.add(obs(I14, I13, I15, sa="low", view="die Unterseite", reason="Lightning oder USB-C"), 1, 1.0)
    first = b.snapshot(1)
    assert first.level == Level.UNSURE and not first.final and first.view_request is not None
    b.add(obs(I14, I13, sa="low", dist=False), 2, 1.0)
    state = b.snapshot(2)
    assert (state.level, state.final, state.view_request) == (Level.UNSURE, True, None)
    assert state.line == "Apple iPhone 14 oder Apple iPhone 13, von außen kaum zu unterscheiden."


def test_readable_model_name_is_decisive():
    b = Belief("de")
    b.add(obs(cand("Myprotein", "Essential BCAA"), readable=("MYPROTEIN", "Essential BCAA 2:1:1"), cat="Dose"), 1, 0.5)
    state = b.snapshot(1)
    assert (state.level, state.final, state.line) == (Level.CERTAIN, True, "Das ist Myprotein Essential BCAA.")


def test_category_only():
    b = Belief("de")
    b.add(obs(desc="rote Keramiktasse", cat="Tasse"), 1, 1.0)
    state = b.snapshot(1)
    assert (state.level, state.final) == (Level.CATEGORY_ONLY, False)
    assert state.display_name == "Rote Keramiktasse"
    assert state.line == "Rote Keramiktasse, ein bestimmtes Produkt erkenne ich nicht."
    b.add(obs(desc="rote Keramiktasse", cat="Tasse"), 2, 1.0)
    assert b.snapshot(2).final


def test_brand_depth_display():
    b = Belief("en")
    b.add(obs(cand("Apple", None, depth="brand")), 1, 1.0)
    assert b.snapshot(1).display_name == "Apple Smartphone"


def test_variant_needs_two_agreeing_observations():
    midnight = cand("Apple", "iPhone 14", depth="variant", variant="Midnight")
    b = Belief("de")
    b.add(obs(midnight), 1, 1.0)
    assert b.snapshot(1).display_name == "Apple iPhone 14"
    b.add(obs(midnight), 2, 1.0)
    assert b.snapshot(2).display_name == "Apple iPhone 14, Midnight"


def test_single_candidate_low_self_assessment():
    b = Belief("de")
    b.add(obs(cand("Sony", "WH-1000XM5"), sa="low", cat="Kopfhörer"), 1, 1.0)
    state = b.snapshot(1)
    assert (state.level, state.line) == (Level.UNSURE, "Vielleicht Sony WH-1000XM5?")


def test_observations_are_kept_in_order():
    b = Belief("de")
    first, second = obs(I14), obs(I13)
    b.add(first, 1, 1.0)
    b.add(second, 2, 1.0)
    assert b.observations == [first, second]
