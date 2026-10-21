import pytest

from yavis import commands
from yavis.apps import AppManager, DEFAULT_APPS
from yavis.config import Settings
from yavis.context import Ctx
from yavis.extras import E
from yavis.memory import Memory


@pytest.fixture
def ctx(tmp_path):
    s = Settings(tmp_path / "s.json")
    c = Ctx(s, Memory(tmp_path / "m.db"), AppManager(s))
    c.timers = []
    c.timer = lambda secs, label: c.timers.append(secs)
    c.clips = []
    c.on_clipboard = c.clips.append
    return c


def test_wake_words():
    names = ["yavis", "jarvis"]
    assert commands.strip_wake("Hey Jarvis, öffne YouTube", names) == (True, "öffne YouTube")
    assert commands.strip_wake("Yavis wie spät ist es", names) == (True, "wie spät ist es")
    assert commands.strip_wake("Yarvis", names) == (True, "")        # Whisper-Variante
    assert commands.strip_wake("Hallo", names) == (True, "")
    assert commands.strip_wake("das Wetter ist schön", names)[0] is False


def test_custom_wake_name():
    assert commands.strip_wake("Computer mach Licht an", ["computer"]) == (True, "mach Licht an")


def test_calc():
    assert commands.safe_calc("2+3*4") == 14
    assert commands.safe_calc("10 geteilt durch 4") == 2.5
    with pytest.raises(Exception):
        commands.safe_calc("__import__('os').system('x')")
    with pytest.raises(Exception):
        commands.safe_calc("9**9**9")


def test_basic_commands(ctx):
    assert "Uhr" in commands.handle("wie spät ist es", ctx)
    assert "ergibt 14" in commands.handle("rechne 2+3*4", ctx)
    assert commands.handle("erzähl mir was über Katzen", ctx) is None
    assert "Gemerkt" in commands.handle("merke dir ich mag Pizza", ctx)
    assert "Pizza" in commands.handle("was weißt du über mich", ctx)
    assert "Timer" in commands.handle("timer 5 minuten", ctx) and ctx.timers == [300]
    commands.handle("passwort erzeugen", ctx)
    assert len(ctx.clips[0]) == 16


def test_mood(ctx):
    commands.handle("sei böse", ctx)
    assert ctx.settings.get("mood") == "boese"
    commands.handle("sei neutral", ctx)
    assert ctx.settings.get("mood") == "neutral"


def test_app_permissions(ctx):
    am = ctx.apps
    assert am.find("den Rechner") == "rechner"
    am.set_allowed(["editor"])
    ok, msg = am.launch("rechner")
    assert not ok and "nicht freigegeben" in msg
    ok, msg = am.launch("gibtsnicht123")
    assert not ok and "kenne" in msg


def test_default_apps_count():
    assert len(DEFAULT_APPS) >= 32


def test_memory_delete(tmp_path):
    m = Memory(tmp_path / "m.db")
    i = m.add("mem", "x")
    m.add("note", "y")
    m.delete(i)
    assert [r[2] for r in m.list()] == ["y"]
    m.clear_all()
    assert m.list() == []


def test_extras():
    assert len(E) >= 46
    assert len({e["name"] for e in E}) == len(E)


def test_game_parsers_and_launch(ctx):
    from yavis import games
    acf = '"AppState"\n{\n\t"appid"\t\t"292030"\n\t"name"\t\t"The Witcher 3: Wild Hunt"\n}'
    assert games.parse_acf(acf) == ("292030", "The Witcher 3: Wild Hunt")
    assert games.parse_acf('"appid" "228980"\n"name" "Steamworks Common Redistributables"') is None
    assert games.parse_libraries('"path"\t\t"D:\\\\Games\\\\Steam"') == ["D:\\Games\\Steam"]
    epic = '{"DisplayName":"Fortnite","AppName":"Fn","CatalogNamespace":"ns","CatalogItemId":"id1"}'
    assert games.parse_epic(epic)[0] == "Fortnite"
    assert games.parse_epic('{"DisplayName":"DLC","AppName":"A","MainGameAppName":"B"}') is None
    ctx.settings.set("games", {"the witcher 3: wild hunt": "steam://rungameid/292030"})
    ctx.apps.set_allowed(["the witcher 3: wild hunt"])
    started = []
    ctx.apps._start = started.append
    assert "Witcher" in commands.handle("starte mein spiel witcher", ctx)
    assert started == ["steam://rungameid/292030"]
    assert "Witcher" in commands.handle("starte spiel", ctx)
    ctx.apps.set_allowed([])
    assert "nicht freigegeben" in commands.handle("spiele witcher", ctx)


def test_voice_catalog():
    from yavis import voices as v
    assert len(v.PROFILES) >= 30
    assert len({p["name"] for p in v.PROFILES}) == len(v.PROFILES)
    assert all(p["base"] in v.BASES for p in v.PROFILES)
    groups = {p["group"] for p in v.PROFILES}
    assert groups == {"Weiblich", "Männlich", "Gefühle"}
    assert v.model_url("kerstin").endswith("/kerstin/low/de_DE-kerstin-low.onnx")
    assert v.profile_by_name(v.DEFAULT_PROFILE)


def test_voice_plan_and_wav(tmp_path):
    import wave
    import numpy as np
    from yavis import voices as v
    prof = v.profile_by_name("Männlich · Karlsson – dominant")
    length, f, gain = v.plan(prof, speed=100, pitch=0, volume=100)
    assert f < 1.0 and abs(length - prof["length"] * f) < 1e-9      # tiefer -> Rate kleiner, Länge ausgeglichen
    assert v.plan(prof, pitch=-99)[1] == 2 ** (-8 / 12)              # Tonhöhe begrenzt
    assert v.plan(prof, speed=200)[0] < v.plan(prof, speed=100)[0]   # schneller -> kürzere length_scale
    src, dst = tmp_path / "a.wav", tmp_path / "b.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes((np.ones(22050, dtype=np.int16) * 10000).tobytes())
    dur = v.process_wav(src, dst, 0.5, 2.0)
    with wave.open(str(dst), "rb") as r:
        assert r.getframerate() == 11025
        assert np.frombuffer(r.readframes(10), dtype=np.int16)[0] == 20000
    assert abs(dur - 2.0) < 0.01
