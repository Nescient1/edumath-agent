from datetime import datetime
from typing import Any


def new_record_id(prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}{stamp}"


WrongQuestionRecord = dict[str, Any]
StudentProfileRecord = dict[str, Any]
