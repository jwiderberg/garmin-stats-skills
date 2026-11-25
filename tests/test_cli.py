from garmin_stats import cli, client, mac, paths, schedule, sync


def test_setup_logs_in_syncs_and_schedules(monkeypatch):
    calls = []

    def fake_login(email, password, prompt_mfa, force=False):
        paths.token_dir().mkdir(parents=True, exist_ok=True)
        paths.token_file().write_text("{}")
        calls.append(("login", email))
        return "Test User"

    monkeypatch.setattr(mac, "is_mac", lambda: True)
    monkeypatch.setattr(mac, "ask", lambda prompt, hidden=False: "pw" if hidden else "a@b.c")
    monkeypatch.setattr(client, "login", fake_login)
    monkeypatch.setattr(
        sync,
        "run",
        lambda cfg, days=None: (
            calls.append(("sync", days))
            or {"ok": True, "refreshed": days, "backfilled": 0, "activities": 1}
        ),
    )
    monkeypatch.setattr(schedule, "install", lambda mins: calls.append(("schedule", mins)))
    assert cli.main(["setup"]) == 0
    assert calls == [("login", "a@b.c"), ("sync", 17), ("schedule", 60)]


def test_setup_stops_if_login_cancelled(monkeypatch):
    def cancel(*a, **k):
        raise mac.Cancelled()

    monkeypatch.setattr(mac, "is_mac", lambda: True)
    monkeypatch.setattr(mac, "ask", cancel)
    assert cli.main(["setup"]) == 1


def test_sync_failure_notifies_once_a_day(monkeypatch):
    notes = []
    monkeypatch.setattr(mac, "is_mac", lambda: True)
    monkeypatch.setattr(mac, "notify", notes.append)
    monkeypatch.setattr(sync, "run", lambda cfg, days=None: {"ok": False, "message": "expired"})
    paths.home().mkdir(parents=True, exist_ok=True)
    assert cli.main(["sync", "--quiet"]) == 1
    assert cli.main(["sync", "--quiet"]) == 1
    assert notes == ["expired"]
