import structlog
import time
from goat.settings import load_settings


def main() -> None:
    settings = load_settings()
    logger = structlog.get_logger(level=settings.APP_MODE)
    logger.info("Settings loaded", settings=settings)

    logger.info("Starting application's main loop -- press Ctrl+C to exit.")

    while True:
        logger.info("Main loop iteration")
        if settings.APP_MODE == "development":
            logger.info("Main loop iteration - development mode - exiting after 1 second")
            time.sleep(1)
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
