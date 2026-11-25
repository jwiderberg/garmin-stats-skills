from datetime import date

import pytest
from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError

from garmin_stats import client, paths

TODAY = date(2026, 5, 10)


class Fake:
    def __init__(self):
        self.calls = 0

    def get_stats(self, d):
        self.calls += 1
        return {"calendarDate": d, "totalSteps": 1000}


def make(fake=None):
    fake = fake or Fake()
    return client.GarminData(factory=lambda: fake, today=lambda: TODAY), fake


def test_past_days_are_cached_on_disk():
    data, fake = make()
    for _ in range(3):
        data.call("get_stats", "2026-05-01", cache_until=date(2026, 5, 1))
    assert fake.calls == 1
    assert list((paths.cache_dir() / "get_stats").glob("*.json"))


def test_today_and_yesterday_are_always_live():
    data, fake = make()
    for d in (date(2026, 5, 10), date(2026, 5, 9)):
        data.call("get_stats", d.isoformat(), cache_until=d)
        data.call("get_stats", d.isoformat(), cache_until=d)
    assert fake.calls == 4


def test_empty_results_are_not_cached():
    class Empty(Fake):
        def get_stats(self, d):
            self.calls += 1
            return {}

    data, fake = make(Empty())
    data.call("get_stats", "2026-05-01", cache_until=date(2026, 5, 1))
    data.call("get_stats", "2026-05-01", cache_until=date(2026, 5, 1))
    assert fake.calls == 2


def test_rate_limit_becomes_friendly_error():
    class Limited(Fake):
        def get_stats(self, d):
            raise GarminConnectTooManyRequestsError("429")

    data, _ = make(Limited())
    with pytest.raises(client.RateLimited):
        data.call("get_stats", "2026-05-09")


def test_auth_error_relogs_once():
    made = []

    class Flaky(Fake):
        def get_stats(self, d):
            if len(made) == 1:
                raise GarminConnectAuthenticationError("expired")
            return {"ok": True}

    def factory():
        made.append(1)
        return Flaky()

    data = client.GarminData(factory=factory, today=lambda: TODAY)
    assert data.call("get_stats", "2026-05-09") == {"ok": True}
    assert len(made) == 2


def test_session_client_without_tokens_says_how_to_login():
    with pytest.raises(client.NotLoggedIn, match="garmin-stats login"):
        client.session_client()


def test_parse_date():
    assert client.parse_date(None, TODAY) == TODAY
    assert client.parse_date("yesterday", TODAY) == date(2026, 5, 9)
    assert client.parse_date("2026-01-02", TODAY) == date(2026, 1, 2)


def test_login_secures_tokens_and_never_stores_password(monkeypatch):
    seen = {}

    class FakeGarmin:
        def __init__(self, email, password, prompt_mfa):
            seen.update(email=email, prompt=prompt_mfa)

        def login(self, tokenstore):
            (paths.token_dir() / "garmin_tokens.json").write_text('{"t": 1}')

        def get_full_name(self):
            return "Test User"

    monkeypatch.setattr(client, "Garmin", FakeGarmin)
    name = client.login("a@b.c", "s3cret", prompt_mfa=lambda: "123456")
    assert name == "Test User" and seen["prompt"]() == "123456"
    assert (paths.token_dir().stat().st_mode & 0o777) == 0o700
    assert (paths.token_file().stat().st_mode & 0o777) == 0o600
    assert "s3cret" not in paths.token_file().read_text()
