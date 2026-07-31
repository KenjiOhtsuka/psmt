import pytest

from psmt.conditional import process_conditionals
from psmt.exceptions import ConditionalError


class TestConditionals:
    def test_if_include(self):
        text = "-- @if dev\nSELECT 1;\n-- @endif\nSELECT 2;"
        assert process_conditionals(text, "dev") == "SELECT 1;\nSELECT 2;"

    def test_if_exclude(self):
        text = "-- @if prod\nSELECT 1;\n-- @endif\nSELECT 2;"
        assert process_conditionals(text, "dev") == "SELECT 2;"

    def test_else(self):
        text = "-- @if prod\nSELECT 1;\n-- @else\nSELECT 2;\n-- @endif"
        assert process_conditionals(text, "dev") == "SELECT 2;"

    def test_else_matches_if(self):
        text = "-- @if prod\nSELECT 1;\n-- @else\nSELECT 2;\n-- @endif"
        assert process_conditionals(text, "prod") == "SELECT 1;"

    def test_not(self):
        text = "-- @if not(prod)\nSELECT 1;\n-- @endif"
        assert process_conditionals(text, "dev") == "SELECT 1;"
        assert process_conditionals(text, "prod") == ""

    def test_not_multiple(self):
        text = "-- @if not(prod, staging)\nSELECT 1;\n-- @endif"
        assert process_conditionals(text, "ci") == "SELECT 1;"
        assert process_conditionals(text, "staging") == ""

    def test_env_list_with_spaces(self):
        text = "-- @if dev, prod\nSELECT 1;\n-- @endif"
        assert process_conditionals(text, "prod") == "SELECT 1;"

    def test_case_sensitive_env(self):
        text = "-- @if Dev\nSELECT 1;\n-- @endif"
        assert process_conditionals(text, "dev") == ""

    def test_nesting(self):
        text = (
            "-- @if dev\n"
            "-- @if not(ci)\n"
            "GRANT ALL ON users TO dev_team;\n"
            "-- @endif\n"
            "-- @endif\n"
        )
        assert process_conditionals(text, "dev") == "GRANT ALL ON users TO dev_team;\n"
        assert process_conditionals(text, "ci") == ""

    def test_unclosed_if(self):
        with pytest.raises(ConditionalError):
            process_conditionals("-- @if dev\nSELECT 1;", "dev")

    def test_endif_without_if(self):
        with pytest.raises(ConditionalError):
            process_conditionals("-- @endif\nSELECT 1;", "dev")

    def test_else_without_if(self):
        with pytest.raises(ConditionalError):
            process_conditionals("-- @else\nSELECT 1;", "dev")

    def test_duplicate_else(self):
        with pytest.raises(ConditionalError):
            process_conditionals("-- @if dev\nSELECT 1;\n-- @else\nX;\n-- @else\nY;\n-- @endif", "dev")

    def test_directive_inside_string_literal(self):
        text = "INSERT INTO t VALUES ('-- @endif');\nSELECT 1;"
        assert process_conditionals(text, "dev") == text

    def test_directive_inside_block_comment(self):
        text = "/*\n-- @endif\n*/\nSELECT 1;"
        assert process_conditionals(text, "dev") == text

    def test_else_binds_innermost(self):
        text = (
            "-- @if dev\n"
            "-- @if ci\n"
            "INNER;\n"
            "-- @else\n"
            "MIDDLE;\n"
            "-- @endif\n"
            "-- @endif\n"
        )
        assert process_conditionals(text, "dev") == "MIDDLE;\n"
