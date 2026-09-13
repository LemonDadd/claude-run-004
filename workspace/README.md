# 中国历法微服务 · Chinese Lunar Calendar Service

公历与农历双向转换、二十四节气查询、传统节日查询、干支纪年与生肖。数据与算法全部内置，
**运行时零第三方历法依赖**；农历数据落于 SQLite，提供 FastAPI HTTP 接口，Docker 一键运行。
适合日历应用、排班系统、文化类产品调用。

- 覆盖范围：**1900-01-31（农历 1900 正月初一）至 2101-01-28（农历 2100 腊月廿九）**
- 农历转换：与独立权威库逐日比对 **73,367 天 0 误差**
- 二十四节气：基于太阳视黄经的天文近似算法，1900–2100 共 4,824 个节气**误差均 ≤ 1 天**
- 批量：HTTP `POST /batch` 10,000 条 **≈ 0.4s**（纯函数 10,000 次 ≈ 0.04s）

---

## 快速开始

### Docker 一键运行

```bash
docker compose up -d --build
# 或
docker build -t lunar-calendar .
docker run -d -p 8000:8000 -v lunar-data:/data lunar-calendar
```

首次启动自动建库并写入 201 年农历数据（约毫秒级），随后直接复用。

### 本地运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开交互式文档：<http://localhost:8000/docs>（Swagger）、<http://localhost:8000/redoc>。

---

## 历法数据与算法

| 模块 | 文件 | 说明 |
|------|------|------|
| 农历数据表 | `app/lunar_data.py` | 1900–2100 每年一个压缩整数（共 201 个） |
| 农历编解码 / 双向转换 / 干支生肖 | `app/calendar.py` | 累计天数 + 二分定位 |
| 二十四节气 | `app/solar_terms.py` | 太阳视黄经 + 牛顿迭代求节，UT+8 取整日 |
| 传统节日 | `app/festivals.py` | 农历固定日 + 节气浮动（清明） |
| SQLite 存储 | `app/db.py` | 表 `lunar_year(year, packed, leap_month, year_days)` |

### 压缩整数编码（17 bit）

```
低 4 位   info & 0xF            闰月月份，0 表示无闰月
bit4..15  (info >> (16-m)) & 1  第 m 个平月大小：0=29 天，1=30 天
bit16     (info >> 16) & 1      闰月大小：0=29 天，1=30 天
```

例如 1900 年 `19416 = 0x4BD8`：低 4 位 = 8 → 闰八月。

### 节气算法

对每个目标黄经（春分点起，小寒 285°、大寒 300°…每隔 15°），以常见公历日为初值，
用 NOAA 低精度太阳视黄经公式迭代到时刻，再换算北京时间（UT+8）向下取整到日。
精度在 1900–2100 全区间满足 ≤ 1 天。

### 干支与生肖

农历年以**春节换年**，六十甲子循环：公元 4 年为甲子年，`index = (农历年 - 4) mod 60`；
生肖与地支一一对应（子鼠…亥猪）。公历元旦至春节前仍属上一农历年，用带 `month/day`
的查询可得到当日确切干支。

---

## API

### `POST /solar-to-lunar` 公历转农历

```bash
curl -X POST localhost:8000/solar-to-lunar \
  -H 'Content-Type: application/json' \
  -d '{"year":2024,"month":2,"day":10}'
```

### `POST /lunar-to-solar` 农历转公历

```bash
curl -X POST localhost:8000/lunar-to-solar \
  -H 'Content-Type: application/json' \
  -d '{"year":2023,"month":2,"day":16,"leap":true}'
```

### `GET /solar-term?year=2024` 某年二十四节气

按公历时间先后（小寒起）返回 24 项，含名称、公历日期、太阳黄经；另附 `seasonal_order`
（立春起的传统节令序）。

### `GET /festival?year=2024` 某年传统节日

春节、元宵、龙抬头、清明、端午、七夕、中元、中秋、重阳、腊八、小年（南/北）、除夕。
自动处理跨年与“除夕在廿九/三十”；清明由节气计算（公历浮动）。

### `GET /ganzhi?year=2024` 干支生肖

- `GET /ganzhi?year=2024`：该公历年春节所开启农历年的干支（含 `spring_festival`）。
- `GET /ganzhi?year=2024&month=2&day=9`：指定公历日期所属农历年（精确到春节换年）。

### `POST /batch` 批量（可混合）

```json
{
  "items": [
    {"op": "solar_to_lunar", "year": 2024, "month": 2, "day": 10},
    {"op": "lunar_to_solar", "year": 2024, "month": 8, "day": 15, "leap": false}
  ]
}
```

每项返回 `{index, ok, result|error}`；单项出错不影响其他项。

### `GET /health`

`{"status":"ok","years":201,"range":"1900-2100"}`

---

## 校验与测试

```bash
pip install -r requirements-dev.txt

# 全量权威校验（农历逐日 + 全部节气，对独立库 lunarcalendar / borax）
PYTHONPATH=. python scripts/validate.py

# 功能与性能测试（含 10000 条 < 1s 断言）
python -m pytest tests/ -q
```

> `lunarcalendar` / `borax` 仅用于**构建期校验**，作为独立第三方基准；
> 生产镜像与运行时不包含、也不依赖它们。

---

## 目录结构

```
app/
  lunar_data.py    # 内置 1900-2100 农历压缩整数表
  calendar.py      # 解码、双向转换、中文名称、干支生肖
  solar_terms.py   # 太阳视黄经节气算法
  festivals.py     # 传统节日
  db.py            # SQLite 存储（启动播种 + 进程缓存）
  schemas.py       # 请求模型
  main.py          # FastAPI 路由
scripts/validate.py
tests/test_calendar.py
Dockerfile  docker-compose.yml  requirements*.txt
```
