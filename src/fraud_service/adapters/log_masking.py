"""Safety net: mask secret values in every log line, even if code logs them by mistake."""
import logging


class MaskSecretsFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret, "**********")
        record.msg, record.args = message, ()
        return True


def install(secrets: list[str]) -> None:
    """Attach the mask to every handler of the root logger (and create one if none exists)."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    mask = MaskSecretsFilter(secrets)
    for handler in root.handlers:
        handler.addFilter(mask)
