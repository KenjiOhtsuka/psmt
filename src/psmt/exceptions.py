class PsmtError(Exception):
    exit_code = 1


class UsageError(PsmtError):
    exit_code = 2


class OperationalError(PsmtError):
    exit_code = 1


class ConfigNotFoundError(OperationalError):
    pass


class DatabaseConfigNotFoundError(OperationalError):
    pass


class DriverNotInstalledError(OperationalError):
    pass


class ConditionalError(OperationalError):
    pass


class MigrationNotFoundError(OperationalError):
    pass
