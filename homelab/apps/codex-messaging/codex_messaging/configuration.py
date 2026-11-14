"""Validate the intentionally keyless first-stage configuration and protected runtime."""


class ConfigurationRejected(Exception):
    """Expose a configuration category without echoing its private values."""

    def __init__(self, code="configuration_invalid"):
        self.code = code
        super().__init__(code)


def keyless_settings(value):
    """No transport, key, provider or operation override can be added to this stage."""
    if (not isinstance(value, dict) or set(value) != {"version", "mode", "user_id", "chat_id"}
            or type(value["version"]) is not int or value["version"] != 1 or value["mode"] != "keyless"
            or any(type(value[name]) is not int or not 0 < value[name] < 2**53 for name in ("user_id", "chat_id"))):
        raise ConfigurationRejected()
    return dict(value)
