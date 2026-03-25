import logging
from logging.handlers import TimedRotatingFileHandler
import os

os.makedirs("logs", exist_ok=True)

handler = TimedRotatingFileHandler(
    filename="logs/bot.log",
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8"
)
handler.suffix = "%Y-%m-%d"

formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)

console = logging.StreamHandler()
console.setFormatter(formatter)

logger = logging.getLogger("badak")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.addHandler(console)
