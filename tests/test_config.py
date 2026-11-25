from garmin_stats import config


def test_defaults_file_created_and_parsed(isolated_home):
    c = config.load()
    assert config.config_file().exists()
    assert c.db_path == isolated_home / "garmin.db"
    assert (c.history_days, c.sync_interval_minutes, c.store_raw) == (365, 60, True)


def test_overrides_and_floors(isolated_home):
    isolated_home.mkdir(parents=True, exist_ok=True)
    config.config_file().write_text(
        'db_path = "~/elsewhere/g.db"\nsync_interval_minutes = 1\nstore_raw = false\n'
    )
    c = config.load()
    assert c.db_path.name == "g.db" and "elsewhere" in str(c.db_path)
    assert c.sync_interval_minutes == 5 and c.store_raw is False
