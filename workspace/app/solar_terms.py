"""二十四节气：基于太阳视黄经的近似天文算法。

思路：对每个节气求太阳视黄经等于目标值（春分点起，每隔 15°）的时刻，
再换算为北京时间并取整到日。1900-2100 年与权威节气表逐日比对，
误差不超过 1 天（脚本 scripts/validate.py 全量校验）。
"""
from __future__ import annotations

import math
from datetime import date
from typing import List

from .lunar_data import MAX_YEAR, MIN_YEAR

# 节气顺序：按公历年内时间先后，从小寒开始（天文口径）
TERMS_CN = [
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分",
    "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
    "小暑", "大暑", "立秋", "处暑", "白露", "秋分",
    "寒露", "霜降", "立冬", "小雪", "大雪", "冬至",
]

# 各节气对应的太阳视黄经（度），与 TERMS_CN 一一对应
_TERM_LAMBDA = [
    285, 300, 315, 330, 345, 0,
    15, 30, 45, 60, 75, 90,
    105, 120, 135, 150, 165, 180,
    195, 210, 225, 240, 255, 270,
]

# 各节气常见的公历日，作为牛顿迭代的初值
_GUESS_DAY = [6, 20, 4, 19, 6, 21, 5, 20, 6, 21, 6, 21,
              7, 23, 8, 23, 8, 23, 8, 24, 7, 22, 7, 22]

# 传统“节令”顺序（立春起），便于文化类产品展示
SEASONAL_ORDER = [
    "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
    "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
    "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
    "立冬", "小雪", "大雪", "冬至", "小寒", "大寒",
]


def _date_to_jd0(y: int, m: int, d: int) -> float:
    """公历日期 0 时（UT）对应的儒略日。"""
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    jdn = d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    return jdn - 0.5


def _jdn_to_date(jdn: float) -> date:
    """儒略日（正午起算的 JDN）转公历日期。"""
    j = int(math.floor(jdn + 0.5))
    a = j + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    dd = (4 * c + 3) // 1461
    e = c - (1461 * dd) // 4
    mm = (5 * e + 2) // 153
    day = e - (153 * mm + 2) // 5 + 1
    month = mm + 3 - 12 * (mm // 10)
    year = 100 * b + dd - 4800 + mm // 10
    return date(year, month, day)


def _apparent_lon(jd: float) -> float:
    """低精度太阳视黄经（NOAA/Astronomical Algorithms 近似），单位度。"""
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + 36000.76983 * t + 0.0003032 * t * t) % 360
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    center = (
        math.sin(m) * (1.914602 - 0.004817 * t - 0.000014 * t * t)
        + math.sin(2 * m) * (0.019993 - 0.00101 * t)
        + math.sin(3 * m) * 0.000289
    )
    omega = math.radians(125.04 - 1934.136 * t)
    return (l0 + center - 0.00569 - 0.00478 * math.sin(omega)) % 360


def term_date(year: int, index: int) -> date:
    """返回某年第 index 个节气（TERMS_CN 顺序）的公历日期。"""
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise ValueError(f"节气年仅支持 {MIN_YEAR}-{MAX_YEAR}，收到 {year}")
    if not 0 <= index < 24:
        raise ValueError("节气序号应为 0..23")
    month = index // 2 + 1
    jd = _date_to_jd0(year, month, _GUESS_DAY[index])
    target = _TERM_LAMBDA[index]
    # 牛顿迭代，太阳黄经平均每天约 0.985647°
    for _ in range(8):
        lon = _apparent_lon(jd)
        diff = (lon - target + 180) % 360 - 180
        if abs(diff) < 1e-8:
            break
        jd -= diff / 0.985647
    # 转北京时间（UT+8）后向下取整到日
    return _jdn_to_date(math.floor(jd + 0.5 + 8 / 24))


def terms_of_year(year: int) -> List[dict]:
    """返回某年全部 24 节气（时间先后顺序），含公历日期与黄经。"""
    return [
        {
            "index": i,
            "name": TERMS_CN[i],
            "solar_date": term_date(year, i).isoformat(),
            "longitude": _TERM_LAMBDA[i],
        }
        for i in range(24)
    ]


def find_term(name: str, year: int) -> date:
    return term_date(year, TERMS_CN.index(name))
