"""中国传统节日查询。

分为两类：
  1. 农历固定日：春节、元宵、龙抬头、端午、七夕、中元、中秋、重阳、腊八、小年、除夕；
  2. 依节气浮动（公历）：清明（太阳视黄经 15°）。
"""
from __future__ import annotations

from typing import List

from . import calendar as cal
from .solar_terms import find_term
from .lunar_data import MAX_YEAR, MIN_YEAR

# (名称, 农历月, 农历日, 是否在腊月最后一天)
_LUNAR_FIXED = [
    ("春节", 1, 1, False),
    ("元宵节", 1, 15, False),
    ("龙抬头", 2, 2, False),
    ("端午节", 5, 5, False),
    ("七夕节", 7, 7, False),
    ("中元节", 7, 15, False),
    ("中秋节", 8, 15, False),
    ("重阳节", 9, 9, False),
    ("腊八节", 12, 8, False),
    ("北方小年", 12, 23, False),
    ("南方小年", 12, 24, False),
]


def festivals_of_year(year: int) -> List[dict]:
    """返回某公历年命中的传统节日。

    采用“公历年归属”：遍历该农历年节日落在公历年 year 的日期，
    并补上一个落在 year 年初、属于上一农历年的除夕（若存在）。
    """
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"年仅支持 {MIN_YEAR}-{MAX_YEAR}，收到 {year}")

    result: dict = {}

    def add(name, sd, ld: cal.LunarDate):
        if sd.year == year:
            result[sd.isoformat()] = {
                "name": name,
                "solar_date": sd.isoformat(),
                "lunar_date": ld.full_cn,
                "lunar": {"year": ld.year, "month": ld.month,
                          "day": ld.day, "leap": ld.leap},
                "type": "lunar",
            }

    # 当年及上一年的农历年（覆盖跨年的春节、除夕）
    for lunar_year in (year - 1, year):
        if not MIN_YEAR <= lunar_year <= MAX_YEAR:
            continue
        for name, m, d, _ in _LUNAR_FIXED:
            try:
                sd = cal.lunar_to_solar(lunar_year, m, d, False)
                add(name, sd, cal.LunarDate(lunar_year, m, d, False))
            except cal.CalendarError:
                continue
        # 除夕：腊月最后一天
        last = cal.last_day_of_lunar_month(lunar_year, 12, False)
        sd = cal.lunar_to_solar(lunar_year, 12, last, False)
        add("除夕", sd, cal.LunarDate(lunar_year, 12, last, False))

    # 清明：节气浮动，恒在公历年内
    qm = find_term("清明", year)
    ld = cal.solar_to_lunar(qm.year, qm.month, qm.day)
    result[qm.isoformat()] = {
        "name": "清明节",
        "solar_date": qm.isoformat(),
        "lunar_date": ld.full_cn,
        "lunar": {"year": ld.year, "month": ld.month,
                  "day": ld.day, "leap": ld.leap},
        "type": "solar_term",
    }

    return [result[k] for k in sorted(result)]
