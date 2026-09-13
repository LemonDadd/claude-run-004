"""构建期全量校验：用独立权威库交叉验证本服务的农历转换与节气。

运行：python scripts/validate.py
- 农历：与 lunarcalendar（独立实现）逐日比对整个支持区间；
- 节气：与 borax 的内置节气表（寿星历系数据）全量比对，误差须 <=1 天。
"""
from __future__ import annotations

import datetime
import sys

from app import calendar as cal
from app import solar_terms as st

failures: list[str] = []


def check_lunar() -> int:
    from lunarcalendar import Converter, Lunar, Solar

    start = datetime.date(1900, 2, 17)
    end = datetime.date(2100, 12, 31)
    d = start
    n = 0
    while d <= end:
        ld = cal.solar_to_lunar(d.year, d.month, d.day)
        ref = Converter.Solar2Lunar(Solar(d.year, d.month, d.day))
        if (ref.year, ref.month, ref.day, bool(ref.isleap)) != (
            ld.year, ld.month, ld.day, ld.leap
        ):
            failures.append(f"lunar mismatch {d}: {ld} vs ref "
                            f"{ref.year}-{ref.month}-{ref.day} leap={ref.isleap}")
        n += 1
        d += datetime.timedelta(days=1)

    # 反向：随机农历日往返
    import random
    random.seed(42)
    for _ in range(50000):
        y = random.randint(cal.MIN_YEAR, cal.MAX_YEAR)
        months = cal.decode_year(y)[1]
        lm = random.choice(months)
        day = random.randint(1, lm.days)
        sd = cal.lunar_to_solar(y, lm.month, day, lm.leap)
        back = cal.solar_to_lunar(sd.year, sd.month, sd.day)
        if (back.year, back.month, back.day, back.leap) != (y, lm.month, day, lm.leap):
            failures.append(f"roundtrip fail {y}-{lm.month}-{day} leap={lm.leap}")
    return n


def check_terms() -> tuple[int, int]:
    from borax.calendars.lunardate import TermUtils

    over_one = 0
    total = 0
    max_err = 0
    for y in range(cal.MIN_YEAR, cal.MAX_YEAR + 1):
        for i in range(24):
            mine = st.term_date(y, i)
            ref = TermUtils._nth_term_day(y, i)
            err = abs((mine - ref).days)
            max_err = max(max_err, err)
            if err > 1:
                over_one += 1
                failures.append(f"term {y} {st.TERMS_CN[i]}: {mine} vs {ref} ({err}d)")
            total += 1
    print(f"节气最大误差 {max_err} 天，超 1 天的个数 {over_one}")
    return total, over_one


if __name__ == "__main__":
    days = check_lunar()
    total_terms, over_one = check_terms()
    print(f"逐日农历比对 {days} 天")
    print(f"节气比对 {total_terms} 个")
    if failures:
        print("校验失败：")
        for f in failures[:20]:
            print("  ", f)
        sys.exit(1)
    print("全部校验通过 ✔（农历逐日一致；节气误差均 ≤ 1 天）")
