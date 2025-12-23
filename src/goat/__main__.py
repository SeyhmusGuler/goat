import structlog
from goat.settings import load_settings


def main() -> None:
    settings = load_settings()
    logger = structlog.get_logger(level=settings.APP_MODE)
    logger.info("Settings loaded", settings=settings)

    while True:
        pass


if __name__ == "__main__":
    main()
