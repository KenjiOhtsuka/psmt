from psmt import generate


class TestSanitize:
    def test_spaces_to_underscore(self):
        assert generate.sanitize_summary("add user table") == "add_user_table"

    def test_invalid_chars_to_underscore(self):
        assert generate.sanitize_summary("add@table!") == "add_table_"

    def test_path_separators(self):
        assert generate.sanitize_summary("a/b\\c") == "a_b_c"

    def test_dotdot_replaced(self):
        assert generate.sanitize_summary("a..b") == "a_b"

    def test_empty(self):
        assert generate.sanitize_summary("") == ""

    def test_already_safe(self):
        assert generate.sanitize_summary("add-user.table") == "add-user.table"


class TestTimestamp:
    def test_17_digits(self):
        ts = generate.utc_timestamp()
        assert len(ts) == 17
        assert ts.isdigit()


class TestCollision:
    def test_same_main_version_retries(self, tmp_path, monkeypatch):
        counts = {"n": 0}

        def fake_now():
            counts["n"] += 1
            return "20260103223344245" if counts["n"] == 1 else "20260103223344246"

        monkeypatch.setattr(generate, "utc_timestamp", fake_now)
        first = tmp_path / "20260103223344245_add"
        first.mkdir()
        name, ts = generate.find_collision_free_name(tmp_path, "other")
        assert counts["n"] == 2
        assert name == "20260103223344246_other"

    def test_same_folder_name_retries(self, tmp_path, monkeypatch):
        counts = {"n": 0}

        def fake_now():
            counts["n"] += 1
            return f"2026010322334424{counts['n'] - 1}"

        monkeypatch.setattr(generate, "utc_timestamp", fake_now)
        (tmp_path / "20260103223344240_add").mkdir()
        name, ts = generate.find_collision_free_name(tmp_path, "add")
        assert counts["n"] == 2
        assert name == "20260103223344241_add"
