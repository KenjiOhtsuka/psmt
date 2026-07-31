import pytest

from psmt.exceptions import UsageError
from psmt.executor.targets import (
    VersionTarget,
    parse_preview_version,
    parse_steps,
    parse_version_list,
)


class TestParseVersionList:
    def test_all(self):
        assert parse_version_list("all") is None

    def test_single_main(self):
        assert parse_version_list("v1") == [VersionTarget("v1")]

    def test_main_sub(self):
        assert parse_version_list("v1:01") == [VersionTarget("v1", "01")]

    def test_multiple(self):
        assert parse_version_list("v1:01, v2:02") == [
            VersionTarget("v1", "01"),
            VersionTarget("v2", "02"),
        ]

    def test_hyphens_allowed(self):
        assert parse_version_list("2026-01-03:release-1") == [
            VersionTarget("2026-01-03", "release-1")
        ]

    def test_uppercase(self):
        assert parse_version_list("V1:01") == [VersionTarget("V1", "01")]

    def test_invalid_empty_element(self):
        with pytest.raises(UsageError):
            parse_version_list("v1,,")

    def test_invalid_bare_sub(self):
        with pytest.raises(UsageError):
            parse_version_list(":01")

    def test_invalid_empty_sub(self):
        with pytest.raises(UsageError):
            parse_version_list("v1:")

    def test_invalid_underscore(self):
        with pytest.raises(UsageError):
            parse_version_list("v_1")

    def test_invalid_space(self):
        with pytest.raises(UsageError):
            parse_version_list("v1 :01")

    def test_invalid_slash(self):
        with pytest.raises(UsageError):
            parse_version_list("v1/01")


class TestParseSteps:
    def test_number(self):
        assert parse_steps("3") == 3

    def test_all(self):
        assert parse_steps("all") is None

    def test_zero(self):
        with pytest.raises(UsageError):
            parse_steps("0")

    def test_negative(self):
        with pytest.raises(UsageError):
            parse_steps("-1")

    def test_non_numeric(self):
        with pytest.raises(UsageError):
            parse_steps("abc")


class TestParsePreviewVersion:
    def test_ok(self):
        assert parse_preview_version("v1:01") == VersionTarget("v1", "01")

    def test_bare_sub_rejected(self):
        with pytest.raises(UsageError):
            parse_preview_version("01")

    def test_bad_part(self):
        with pytest.raises(UsageError):
            parse_preview_version("v1:a_b")
