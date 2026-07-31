import pytest

from psmt.naming import (
    classify_file,
    classify_folder,
    collect_files,
    find_do_undo,
    parse_file,
    parse_folder,
)


class TestParseFolder:
    def test_valid(self):
        assert parse_folder("20260103223344245_add_users_table") == (
            "20260103223344245",
            "add_users_table",
        )

    def test_alpha_main_version(self):
        assert parse_folder("2026-alpha-01_add_users") == ("2026-alpha-01", "add_users")

    def test_no_underscore(self):
        assert parse_folder("badfolder") is None

    def test_empty_main_version(self):
        assert parse_folder("_add_users") is None

    def test_empty_description(self):
        assert parse_folder("20260101_") is None

    def test_invalid_main_version_charset(self):
        assert parse_folder("bad/name_x") is None

    def test_invalid_description_charset(self):
        assert parse_folder("20260101_bad desc") is None

    def test_description_with_underscore_and_dot(self):
        assert parse_folder("v1_a.b_c") == ("v1", "a.b_c")


class TestParseFile:
    def test_valid(self):
        assert parse_file("01_create_users__do.sql") == ("01", "create_users", "do")

    def test_valid_undo(self):
        assert parse_file("02_add_email_index__undo.sql") == ("02", "add_email_index", "undo")

    def test_direction_case_sensitive(self):
        assert parse_file("01_x__DO.sql") is None

    def test_extension_uppercase(self):
        assert parse_file("01_x__do.SQL") is None

    def test_non_sql_extension(self):
        assert parse_file("01_x__do.txt") is None

    def test_no_direction_separator(self):
        assert parse_file("01_x_do.sql") is None

    def test_bad_direction(self):
        assert parse_file("01_x__side.sql") is None

    def test_alpha_sub_version(self):
        assert parse_file("alpha-1_create__do.sql") == ("alpha-1", "create", "do")

    def test_description_with_double_underscore(self):
        assert parse_file("01_add__users__do.sql") == ("01", "add__users", "do")


class TestClassification:
    def test_classify_file_non_conforming_sql(self, tmp_path):
        f = classify_file(None, tmp_path / "01_x__DO.sql")
        assert f is not None and not f.conforming

    def test_classify_file_non_sql_ignored(self, tmp_path):
        assert classify_file(None, tmp_path / "README.md") is None

    def test_classify_folder_empty_main_version(self, tmp_path):
        f = classify_folder(tmp_path / "_x")
        assert not f.conforming
        assert "empty main_version" in f.reason


def test_find_do_undo_pairs():
    class Fake:
        pass

    do = Fake()
    do.prefix = "01_x"
    do.direction = "do"
    undo = Fake()
    undo.prefix = "01_x"
    undo.direction = "undo"
    only_do = Fake()
    only_do.prefix = "02_y"
    only_do.direction = "do"
    pairs = find_do_undo([do, undo, only_do])
    assert set(pairs["01_x"]) == {"do", "undo"}
    assert "undo" not in pairs["02_y"]
