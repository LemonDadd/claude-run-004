"""功能与性能测试（不依赖第三方历法库）。"""
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import calendar as cal
from app import solar_terms as st
from app.main import app

client = TestClient(app)


# ---------------- 权威已知样例（春节日期来自公开历书） ----------------
SPRING_FESTIVALS = {
    1900: date(1900, 1, 31),
    1984: date(1984, 2, 2),
    2000: date(2000, 2, 5),
    2023: date(2023, 1, 22),
    2024: date(2024, 2, 10),
    2025: date(2025, 1, 29),
    2033: date(2033, 1, 31),
    2100: date(2100, 2, 9),
}


def test_spring_festival_dates():
    for y, sd in SPRING_FESTIVALS.items():
        assert cal.lunar_to_solar(y, 1, 1, False) == sd


def test_specific_festivals():
    # 2024 中秋 9-17，端午 6-10
    assert cal.lunar_to_solar(2024, 8, 15) == date(2024, 9, 17)
    assert cal.lunar_to_solar(2024, 5, 5) == date(2024, 6, 10)
    # 2023 闰二月
    assert cal.leap_month(2023) == 2
    assert cal.leap_month(2024) == 0


def test_roundtrip_full_range():
    d = date(1900, 1, 31)
    end = date(2100, 12, 31)
    while d <= end:
        ld = cal.solar_to_lunar(d.year, d.month, d.day)
        back = cal.lunar_to_solar(ld.year, ld.month, ld.day, ld.leap)
        assert back == d
        d += date.resolution
        if d.year > 2100:  # 限制用例时长可选；这里全量
            pass


def test_ganzhi_zodiac():
    assert cal.ganzhi_of_year(2024)["ganzhi"] == "甲辰"
    assert cal.ganzhi_of_year(2024)["zodiac"] == "龙"
    assert cal.ganzhi_of_year(2025)["ganzhi"] == "乙巳"
    assert cal.ganzhi_of_year(2023)["ganzhi"] == "癸卯"
    assert cal.ganzhi_of_year(1984)["ganzhi"] == "甲子"


def test_solar_terms_known():
    assert st.term_date(2024, st.TERMS_CN.index("清明")) == date(2024, 4, 4)
    assert st.term_date(2023, st.TERMS_CN.index("冬至")) == date(2023, 12, 22)
    assert st.term_date(2000, st.TERMS_CN.index("立春")) == date(2000, 2, 4)


def test_terms_all_dates():
    # 节气必须落在其对应公历月份
    for y in (1900, 1950, 2024, 2099, 2100):
        for i in range(24):
            td = st.term_date(y, i)
            assert td.month == i // 2 + 1


def test_cn_names():
    ld = cal.solar_to_lunar(2024, 2, 10)  # 春节正月初一
    assert ld.month_cn == "正月"
    assert ld.day_cn == "初一"
    assert ld.full_cn == "2024年正月初一"
    ld2 = cal.LunarDate(2024, 8, 15)
    assert ld2.day_cn == "十五"
    assert cal.LunarDate(2024, 12, 30).day_cn == "三十"


def test_invalid_inputs():
    with pytest.raises(cal.CalendarError):
        cal.solar_to_lunar(1899, 12, 31)
    with pytest.raises(cal.CalendarError):
        cal.lunar_to_solar(2024, 1, 30)  # 2024 正月仅 29 天
    with pytest.raises(cal.CalendarError):
        cal.lunar_to_solar(2024, 3, 1, True)  # 2024 无闰三月


# ---------------- HTTP 接口 ----------------
def test_http_conversions():
    r = client.post("/solar-to-lunar", json={"year": 2024, "month": 2, "day": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["lunar"]["month"] == 1 and body["lunar"]["day"] == 1

    r2 = client.post("/lunar-to-solar",
                     json={"year": 2024, "month": 8, "day": 15, "leap": False})
    assert r2.json()["solar"]["date"] == "2024-09-17"


def test_http_term_festival_ganzhi():
    terms = client.get("/solar-term", params={"year": 2024}).json()["terms"]
    assert len(terms) == 24

    f = client.get("/festival", params={"year": 2024}).json()["festivals"]
    names = {x["name"] for x in f}
    assert {"春节", "端午节", "中秋节", "除夕", "清明节"} <= names

    g = client.get("/ganzhi", params={"year": 2024}).json()
    assert g["ganzhi"] == "甲辰" and g["zodiac"] == "龙"


def test_batch_performance_10000():
    items = []
    for i in range(10000):
        y = 1901 + (i % 200)
        items.append({"op": "solar_to_lunar", "year": y,
                      "month": 1 + (i % 12), "day": 1 + (i % 28)})
    t0 = time.perf_counter()
    r = client.post("/batch", json={"items": items})
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 10000
    assert all(x["ok"] for x in data["results"])
    assert elapsed < 1.0, f"批量耗时 {elapsed:.3f}s 超过 1s"


def test_batch_mixed_and_bad():
    items = [
        {"op": "lunar_to_solar", "year": 2024, "month": 1, "day": 1},
        {"op": "solar_to_lunar", "year": 2024, "month": 6, "day": 10},
        {"op": "bogus", "year": 2024, "month": 1, "day": 1},
        {"op": "lunar_to_solar", "year": 2024, "month": 1, "day": 30},
    ]
    res = client.post("/batch", json={"items": items}).json()["results"]
    assert res[0]["ok"] and res[1]["ok"]
    assert not res[2]["ok"] and not res[3]["ok"]
