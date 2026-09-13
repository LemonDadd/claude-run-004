"""历法微服务：公历/农历双向转换、节气、节日、干支生肖、批量。"""
from __future__ import annotations

from datetime import date

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from . import calendar as cal
from . import festivals as fests
from . import solar_terms as st
from .db import get_store
from .lunar_data import MAX_YEAR, MIN_YEAR
from .schemas import BatchRequest, LunarDateIn, SolarDateIn


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 触发建表/播种，并预热农历累计缓存
    store = get_store()
    assert store.count() == MAX_YEAR - MIN_YEAR + 1
    cal._cumulative()
    yield
    store.close()


app = FastAPI(
    title="中国历法服务",
    description="公历/农历双向转换、二十四节气、传统节日、干支生肖（1900-2100）",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(cal.CalendarError)
def _calendar_error_handler(_request, exc: cal.CalendarError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


# ---------------------------------------------------------------------------
# 序列化辅助
# ---------------------------------------------------------------------------

def _lunar_payload(ld: cal.LunarDate) -> dict:
    return {
        "lunar": {
            "year": ld.year,
            "month": ld.month,
            "day": ld.day,
            "leap": ld.leap,
            "month_cn": ld.month_cn,
            "day_cn": ld.day_cn,
            "display": ld.full_cn,
        },
        "ganzhi": cal.ganzhi_of_year(ld.year),
    }


def _solar_payload(sd: date, ld: cal.LunarDate) -> dict:
    return {
        "solar": {"year": sd.year, "month": sd.month, "day": sd.day,
                  "date": sd.isoformat(), "weekday": sd.isoweekday()},
        **_lunar_payload(ld),
    }


# ---------------------------------------------------------------------------
# 转换接口
# ---------------------------------------------------------------------------

@app.post("/solar-to-lunar", summary="公历转农历")
def solar_to_lunar(body: SolarDateIn):
    try:
        sd = date(body.year, body.month, body.day)
        ld = cal.solar_to_lunar(sd.year, sd.month, sd.day)
    except ValueError as exc:  # 非法公历日
        raise HTTPException(status_code=400, detail=f"无效日期：{exc}")
    return _solar_payload(sd, ld)


@app.post("/lunar-to-solar", summary="农历转公历")
def lunar_to_solar(body: LunarDateIn):
    sd = cal.lunar_to_solar(body.year, body.month, body.day, body.leap)
    ld = cal.LunarDate(body.year, body.month, body.day, body.leap)
    return _solar_payload(sd, ld)


# ---------------------------------------------------------------------------
# 节气 / 节日 / 干支
# ---------------------------------------------------------------------------

@app.get("/solar-term", summary="查询某年二十四节气")
def solar_term(year: int = Query(..., ge=MIN_YEAR, le=MAX_YEAR)):
    return {
        "year": year,
        "order": "chronological",
        "terms": st.terms_of_year(year),
        "seasonal_order": st.SEASONAL_ORDER,
    }


@app.get("/festival", summary="查询某年传统节日")
def festival(year: int = Query(..., ge=MIN_YEAR, le=MAX_YEAR)):
    return {"year": year, "festivals": fests.festivals_of_year(year)}


@app.get("/ganzhi", summary="查询干支生肖")
def ganzhi(year: int = Query(..., description="公历年；以春节换年，返回该农历年干支"),
           month: int | None = Query(None, ge=1, le=12),
           day: int | None = Query(None, ge=1, le=31)):
    # 给出具体月日时按当日所属农历年；否则返回该公历年“春节所在农历年”的干支
    if month is not None and day is not None:
        try:
            return cal.ganzhi_at(year, month, day)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效日期：{exc}")
    spring = cal.lunar_to_solar(year, 1, 1, False)
    # 默认返回该公历年“春节所开启”的农历年干支；春节前日期请带 month/day 精确查询
    g = cal.ganzhi_of_year(year)
    g["spring_festival"] = spring.isoformat()
    return g


# ---------------------------------------------------------------------------
# 批量
# ---------------------------------------------------------------------------

@app.post("/batch", summary="批量转换（solar_to_lunar / lunar_to_solar 混合）")
def batch(body: BatchRequest):
    results = []
    for i, item in enumerate(body.items):
        try:
            if item.op == "solar_to_lunar":
                sd = date(item.year, item.month, item.day)
                ld = cal.solar_to_lunar(sd.year, sd.month, sd.day)
                results.append({"index": i, "ok": True, "result": _solar_payload(sd, ld)})
            elif item.op == "lunar_to_solar":
                sd = cal.lunar_to_solar(item.year, item.month, item.day, bool(item.leap))
                ld = cal.LunarDate(item.year, item.month, item.day, bool(item.leap))
                results.append({"index": i, "ok": True, "result": _solar_payload(sd, ld)})
            else:
                results.append({"index": i, "ok": False,
                                "error": f"未知 op: {item.op}"})
        except (ValueError, cal.CalendarError) as exc:
            results.append({"index": i, "ok": False, "error": str(exc)})
    return {"count": len(results), "results": results}


@app.get("/health", summary="健康检查")
def health():
    return {"status": "ok", "years": get_store().count(),
            "range": f"{MIN_YEAR}-{MAX_YEAR}"}
