import pytest

from psmt import sqlscan


def code_positions(text):
    kinds = sqlscan.classify(text)
    return [i for i, k in enumerate(kinds) if k == sqlscan.CTX_CODE]


class TestClassify:
    def test_simple(self):
        assert code_positions("SELECT 1") == [0, 1, 2, 3, 4, 5, 6, 7]

    def test_string_not_code(self):
        assert 3 not in code_positions("'abc'")

    def test_escaped_quote(self):
        text = "'it''s'"
        positions = code_positions(text)
        assert 0 not in positions and len(text) - 1 not in positions

    def test_backslash_escape_e_string(self):
        text = "E'it\\'s'"
        positions = code_positions(text)
        assert 1 not in positions
        assert all(i not in positions for i in range(2, len(text)))

    def test_plain_string_backslash_not_escape(self):
        text = "'a\\b'"
        positions = code_positions(text)
        assert 4 not in positions

    def test_dollar_quote(self):
        text = "$$ body 'x' $$"
        positions = code_positions(text)
        assert 0 not in positions and len(text) - 1 not in positions

    def test_dollar_quote_with_tag(self):
        text = "$fn$ SELECT 'a' $fn$"
        assert 0 not in code_positions(text)

    def test_line_comment(self):
        text = "-- @if dev\nSELECT 1"
        positions = code_positions(text)
        assert 0 not in positions
        assert positions and positions[0] == len("-- @if dev")

    def test_block_comment(self):
        text = "/* x\nCOMMIT\n*/ SELECT 1"
        positions = code_positions(text)
        assert text.find("COMMIT") not in positions
        assert text.find("SELECT") in positions

    def test_nested_block_comment(self):
        text = "/* a /* b */ c */ SELECT 1"
        positions = code_positions(text)
        comment_end = len("/* a /* b */ c */")
        assert all(i not in positions for i in range(comment_end))
        assert text.find("SELECT") in positions

    def test_delimited_identifier(self):
        text = '"select"'
        assert 0 not in code_positions(text)

    def test_backtick_identifier(self):
        text = "`select`"
        assert 0 not in code_positions(text)

    def test_bracket_identifier(self):
        text = "[select]"
        assert 0 not in code_positions(text)

    def test_mysql_hash_comment_at_line_start(self):
        text = "# note\nSELECT 1"
        positions = code_positions(text)
        assert all(i not in positions for i in range(len("# note")))
        assert text.find("SELECT") in positions

    def test_hash_mid_line_not_comment(self):
        text = "SELECT 1 #> 'a'"
        positions = code_positions(text)
        assert text.find("#") in positions


class TestSplitStatements:
    def test_basic(self):
        assert sqlscan.split_statements("SELECT 1; SELECT 2;") == ["SELECT 1", "SELECT 2"]

    def test_semicolon_in_string(self):
        text = "INSERT INTO t VALUES ('a;b'); SELECT 1;"
        assert sqlscan.split_statements(text) == [
            "INSERT INTO t VALUES ('a;b')",
            "SELECT 1",
        ]

    def test_semicolon_in_comment(self):
        text = "SELECT 1; /* x; y */ SELECT 2;"
        assert sqlscan.split_statements(text) == ["SELECT 1", "/* x; y */ SELECT 2"]

    def test_trailing_statement_without_semicolon(self):
        assert sqlscan.split_statements("SELECT 1; SELECT 2") == ["SELECT 1", "SELECT 2"]

    def test_empty_statements_ignored(self):
        assert sqlscan.split_statements(";;SELECT 1;;") == ["SELECT 1"]


class TestLineStartsInCode:
    def test_line_inside_block_comment(self):
        text = "/* x\nCOMMIT\n*/\nSELECT 1"
        starts = sqlscan.line_starts_in_code(text)
        assert starts[1] is False

    def test_line_inside_string(self):
        text = "'a\nCOMMIT\nb'"
        starts = sqlscan.line_starts_in_code(text)
        assert starts[1] is False

    def test_normal_line(self):
        assert sqlscan.line_starts_in_code("COMMIT\nSELECT 1") == [True, True]


class TestFirstWords:
    def test_leading_comment_skipped(self):
        assert sqlscan.first_words("-- hi\ncreate table t (id int)", 2) == ["CREATE", "TABLE"]

    def test_case_insensitive(self):
        assert sqlscan.first_words("insert into x values (1)", 2) == ["INSERT", "INTO"]
