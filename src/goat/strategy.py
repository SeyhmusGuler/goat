from enum import StrEnum
from pydantic import BaseModel


class StrategyID(StrEnum):
    pass


class Strategy(BaseModel):
    id: StrategyID
