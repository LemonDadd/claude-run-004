"""农历历法核心：压缩整数解码、公历/农历双向转换、中文名称、干支与生肖。

仅依赖内置的 app.lunar_data.YEAR_INFOS，运行时不需要任何第三方历法库。
转换基准：农历 1900 年正月初一 = 公历 1900-01-31。
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import List, Tuple

from .lunar_data import MAX_YEAR, MIN_YEAR, YEAR_INFOS

# ---------------------------------------------------------------------------
# 常量与名称
# ---------------------------------------------------------------------------

_BASE_SOLAR = date(1900, 1, 31)  # 农历 1900-01-01 对应的公历日期

MONTHS_CN = ["", "正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
DAY_TENS = ["初", "十", "廿", "卅"]
DAY_UNITS = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
ZODIACS = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

# 六十甲子（干支纪年用）
SEXAGENARY = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]
# 公元 4 年 = 甲子年，故 (year - 4) % 60
GANZHI_EPOCH = 4


class CalendarError(ValueError):
    """历法参数越界或非法。"""


# ---------------------------------------------------------------------------
# 压缩整数解码
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LunarMonth:
    month: int       # 月份 1..12
    days: int        # 该月天数 29 / 30
    leap: bool       # 是否闰月


def decode_year(year: int) -> Tuple[int, List[LunarMonth]]:
    """返回 (闰月月份, 该农历年按月序排列的月份列表)。"""
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise CalendarError(f"农历年仅支持 {MIN_YEAR}-{MAX_YEAR}，收到 {year}")
    info = YEAR_INFOS[year - MIN_YEAR]
    leap_month = info & 0xF
    leap_days = 29 + ((info >> 16) & 1) if leap_month else 0

    months: List[LunarMonth] = []
    for m in range(1, 13):
        months.append(LunarMonth(m, 29 + ((info >> (16 - m)) & 1), False))
        if leap_month == m:
            months.append(LunarMonth(m, leap_days, True))
    return leap_month, months


def year_days(year: int) -> int:
    return sum(m.days for m in decode_year(year)[1])


@lru_cache(maxsize=1)
def _cumulative() -> List[int]:
    """cum[i] = 第 MIN_YEAR+i 个农历年正月初一相对基准的天数；末项为越界哨兵。"""
    cum = [0]
    for y in range(MIN_YEAR, MAX_YEAR + 1):
        cum.append(cum[-1] + year_days(y))
    return cum


# ---------------------------------------------------------------------------
# 公历 <-> 农历
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LunarDate:
    year: int
    month: int
    day: int
    leap: bool = False

    # ---- 中文展示 ----
    @property
    def month_cn(self) -> str:
        return ("闰" if self.leap else "") + MONTHS_CN[self.month] + "月"

    @property
    def day_cn(self) -> str:
        d = self.day
        if d == 10:
            return "初十"
        if d == 20:
            return "二十"
        if d == 30:
            return "三十"
        return DAY_TENS[(d - 1) // 10] + DAY_UNITS[d % 10]

    @property
    def full_cn(self) -> str:
        return f"{self.year}年{self.month_cn}{self.day_cn}"


def solar_to_lunar(y: int, m: int, d: int) -> LunarDate:
    sd = date(y, m, d)  # 非法日期会抛 ValueError
    cum = _cumulative()
    offset = (sd - _BASE_SOLAR).days
    if offset < 0 or offset >= cum[-1]:
        raise CalendarError(
            f"公历 {y}-{m:02d}-{d:02d} 超出支持范围（约 1900-01-31 至 2101-01-28）"
        )
    yi = bisect.bisect_right(cum, offset) - 1
    rem = offset - cum[yi]
    lunar_year = MIN_YEAR + yi
    for lm in decode_year(lunar_year)[1]:
        if rem < lm.days:
            return LunarDate(lunar_year, lm.month, rem + 1, lm.leap)
        rem -= lm.days
    raise CalendarError("内部错误：未定位到农历月")  # pragma: no cover


def lunar_to_solar(year: int, month: int, day: int, leap: bool = False) -> date:
    _, months = decode_year(year)
    offset = _cumulative()[year - MIN_YEAR]
    for lm in months:
        if lm.month == month and lm.leap == leap:
            if not 1 <= day <= lm.days:
                raise CalendarError(
                    f"农历 {year}年{'闰' if leap else ''}{month}月没有 {day} 日"
                    f"（该月共 {lm.days} 天）"
                )
            return _BASE_SOLAR + timedelta(days=offset + day - 1)
        offset += lm.days
    raise CalendarError(f"农历 {year} 年不存在{'闰' if leap else ''}{month} 月")


def last_day_of_lunar_month(year: int, month: int, leap: bool = False) -> int:
    for lm in decode_year(year)[1]:
        if lm.month == month and lm.leap == leap:
            return lm.days
    raise CalendarError(f"农历 {year} 年不存在该月")


# ---------------------------------------------------------------------------
# 干支与生肖
# ---------------------------------------------------------------------------

def leap_month(year: int) -> int:
    return decode_year(year)[0]


def ganzhi_of_year(lunar_year: int) -> dict:
    """返回某农历年（以春节为岁首）的干支与生肖。

    农历年用六十甲子纪年：公元 4 年为甲子年，故 (year-4)%60。
    生肖与地支一一对应。注意：公历年元旦到春节前仍属于上一个农历年。
    """
    if not MIN_YEAR <= lunar_year <= MAX_YEAR + 1:
        raise CalendarError(f"干支年仅支持农历 {MIN_YEAR}-{MAX_YEAR + 1} 年")
    idx = (lunar_year - GANZHI_EPOCH) % 60
    return {
        "lunar_year": lunar_year,
        "ganzhi": SEXAGENARY[idx],
        "stem": STEMS[idx % 10],
        "branch": BRANCHES[idx % 12],
        "zodiac": ZODIACS[idx % 12],
        "index": idx + 1,  # 在六十甲子中的位次，1..60
    }


def ganzhi_at(y: int, m: int, d: int) -> dict:
    """给定公历日期，按“春节换年”返回当日所属农历年的干支生肖。"""
    ld = solar_to_lunar(y, m, d)
    g = ganzhi_of_year(ld.year)
    g["solar_date"] = f"{y:04d}-{m:02d}-{d:02d}"
    return g
