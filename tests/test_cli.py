from garmin_stats import cli, client, config, mac, paths, schedule, sync


def _fake_login(calls):
    def login(email, password, prompt_mfa, force=False):
        paths.token_dir().mkdir(parents=True, exist_ok=True)
        paths.token_file().write_text("{}")
        calls.append(("login", email))
        return "Test User"

    return login


def test_setup_signs_in_asks_days_schedules_then_imports(monkeypatch):
    calls = []

    def fake_run(cfg, days=None, patient=False, progress=None):
        calls.append(("sync", days, patient))
        return {"ok": True, "refreshed": days, "backfilled": 0, "activities": 1}

    monkeypatch.setattr(mac, "is_mac", lambda: True)
    monkeypatch.setattr(mac, "ask", lambda prompt, hidden=False: "pw" if hidden else "a@b.c")
    monkeypatch.setattr(mac, "choose", lambda prompt, buttons, default: "60 days")
    monkeypatch.setattr(client, "login", _fake_login(calls))
    monkeypatch.setattr(sync, "run", fake_run)
    monkeypatch.setattr(schedule, "install", lambda mins: calls.append(("schedule", mins)))

    assert cli.main(["setup"]) == 0
    # schedule BEFORE the import, so closing Terminal mid-import is safe
    assert calls == [("login", "a@b.c"), ("schedule", 60), ("sync", 60, True)]
    assert config.load().history_days == 60


def test_setup_stops_if_login_cancelled(monkeypatch):
    def cancel(*a, **k):
        raise mac.Cancelled()

    monkeypatch.setattr(mac, "is_mac", lambda: True)
    monkeypatch.setattr(mac, "ask", cancel)
    monkeypatch.setattr(sync, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert cli.main(["setup"]) == 1


def test_sync_failure_notifies_once_a_day(monkeypatch):
    notes = []
    monkeypatch.setattr(mac, "is_mac", lambda: True)
    monkeypatch.setattr(mac, "notify", notes.append)
    monkeypatch.setattr(sync, "run", lambda cfg, **k: {"ok": False, "message": "expired"})
    paths.home().mkdir(parents=True, exist_ok=True)
    assert cli.main(["sync", "--quiet"]) == 1
    assert cli.main(["sync", "--quiet"]) == 1
    assert notes == ["expired"]


def test_progress_line_is_readable(capsys):
    p = cli._printer()
    p(
        "day",
        i=1,
        n=30,
        date="2026-05-20",
        row={"sleep_score": 81, "hrv_last_night_ms": 55.4, "resting_hr": 50, "steps": 9120},
    )
    p("pause", seconds=180)
    out = capsys.readouterr().out
    assert "[  1/30] 2026-05-20  sleep 81 · HRV 55 · RHR 50 · 9,120 steps" in out
    assert "Waiting 3 min" in out
