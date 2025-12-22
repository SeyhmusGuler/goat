from enum import StrEnum
from pydantic import AwareDatetime


class Symbol(StrEnum):
    pass


class DateTime(AwareDatetime):
    pass
