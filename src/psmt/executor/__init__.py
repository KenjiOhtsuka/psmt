from dataclasses import dataclass

from ..logging import Logger


@dataclass
class MigrationContext:
    logger: Logger
    env: str
    db_key: str
    cfg: object
    driver: object
    migrations_dir: object
