import pytest

from psmt.config import DatabaseConfig
from psmt.drivers.registry import get_driver

from tests.integration.helpers import (
    DOCKER,
    ENGINES,
    TEST_DATABASE,
    create_config,
    make_context,
    server_available,
)


@pytest.fixture
def engine_ready(tmp_path):
    def _require(engine):
        cfg = create_config(engine, tmp_path)
        reason = server_available(cfg)
        if reason:
            pytest.skip(reason)
        return cfg

    return _require
