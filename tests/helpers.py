import random
import string
from datetime import datetime, timezone


def rand_str(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
