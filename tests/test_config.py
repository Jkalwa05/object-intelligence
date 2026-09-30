import pytest

from oi.config import Settings


def test_defaults_match_spec():
    s = Settings()
    assert (s.model, s.effort, s.language) == ("claude-opus-5-5", "low", "de")
    assert (s.max_calls_object, s.max_calls_session, s.max_concurrent_calls) == (4, 150, 2)
    assert (s.min_sharpness, s.dhash_min_distance, s.crop_long_edge, s.port) == (60.0, 14, 1024, 8766)
    assert s.focus_weights == (0.30, 0.20, 0.25, 0.15, 0.10)


def test_env_overrides():
    s = Settings.from_env({"OI_MODEL": "claude-sonnet-5-5", "OI_MAX_CALLS_SESSION": "10", "OI_MIN_SHARPNESS": "80",
                           "OI_LOG_CALLS": "0", "OI_LANGUAGE": "en", "OI_PORT": "9000"})
    assert (s.model, s.max_calls_session, s.min_sharpness, s.log_calls, s.language, s.port) == \
        ("claude-sonnet-5-5", 10, 80.0, False, "en", 9000)


def test_env_without_overrides_gives_defaults():
    assert Settings.from_env({}) == Settings()


@pytest.mark.parametrize("env", [{"OI_LANGUAGE": "fr"}, {"OI_MODEL": "gpt-5"}])
def test_invalid_values_rejected(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)
