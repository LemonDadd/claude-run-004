"""请求/响应模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SolarDateIn(BaseModel):
    year: int = Field(..., ge=1, le=9999)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)


class LunarDateIn(BaseModel):
    year: int = Field(..., description="农历年")
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=30)
    leap: bool = Field(False, description="是否闰月")


class BatchItem(BaseModel):
    op: str = Field(..., description="solar_to_lunar | lunar_to_solar")
    year: int
    month: int
    day: int
    leap: Optional[bool] = False


class BatchRequest(BaseModel):
    items: list[BatchItem]
