
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException

socket.setdefaulttimeout(90)  



zones = {
    "Arsi":      {"lat": 7.958243,  "lon": 39.124205},
    "Bale,Robe": {"lat": 7.1242676, "lon": 40.0080973},
    "Jimma":     {"lat": 7.67783,   "lon": 36.833164},
}


ENABLE_NDVI = os.getenv("ENABLE_NDVI") == "1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
F_RAIN_DAILY = f"{DATA_DIR}/rain_daily_final.csv"
F_RAIN_LATE = f"{DATA_DIR}/rain_daily_late.csv"
F_RAIN_MONTHLY = f"{DATA_DIR}/rain_monthly.csv"
F_POWER = f"{DATA_DIR}/power_daily.csv"
F_NDVI = f"{DATA_DIR}/ndvi.csv"
F_ELEV = f"{DATA_DIR}/elevation.json"

POWER_PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M", "GWETTOP", "GWETROOT", "GWETPROF"]
POWER_FIRST = "2000-01-01"
RAIN_MONTHLY_FIRST = "2000-01-01"
RAIN_DAILY_FIRST = "2000-06-01"      
NDVI_FIRST = "2000-01-01"
NDVI_CHUNK = int(os.getenv("NDVI_CHUNK", "3"))   

MODIS = "https://modis.ornl.gov/rst/api/v1"
MODIS_HEADERS = {"Accept": "application/json"}


def utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def http_json(url, params, tries=4, timeout=(15, 90), headers=None, backoff=5):
    """GET + retry. Returns parsed JSON or None."""
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            wait = backoff * (attempt + 1)
            resp = getattr(e, "response", None)
            detail = f" {resp.status_code}: {resp.text[:200]}" if resp is not None else ""
            last = attempt == tries - 1
            print(f"  request failed ({type(e).__name__}{detail})" + ("" if last else f", retry {attempt + 1}/{tries} in {wait}s"))
            if not last:
                time.sleep(wait)
    return None


def save_csv(df, path, tries=5):
    """Write to a temp file, then swap it in. Retries if OneDrive/Excel has the file locked."""
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    for attempt in range(tries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            print(f"  {path} is locked (open in Excel? OneDrive syncing?), retry {attempt + 1}/{tries}")
            time.sleep(3)
    raise PermissionError(
        f"Cannot write {path}. Close it in Excel/VS Code or pause OneDrive, then re-run "
        f"(your new data is kept in {tmp}).")



# NASA POWER (temperature, humidity, soil wetness)

def get_power(lat, lon, params, start, end, tries=4, timeout=60):
    """start/end as YYYYMMDD. Returns a DataFrame indexed by date."""
    d = http_json(
        "https://power.larc.nasa.gov/api/temporal/daily/point",
        {"parameters": ",".join(params), "community": "AG",
         "latitude": lat, "longitude": lon,
         "start": start, "end": end, "format": "JSON"},
        timeout=timeout, tries=tries,
    )
    if d is None:
        raise RuntimeError("NASA POWER request failed")
    df = pd.DataFrame(d["properties"]["parameter"])
    df.index = pd.to_datetime(df.index)
    return df.replace(-999, np.nan)


def get_weather_soil(lat, lon, days=60):
    end = datetime.now(timezone.utc).strftime("%Y%m%d")
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    return get_power(lat, lon, POWER_PARAMS, start, end, tries=2, timeout=20).dropna()


def build_power():
    os.makedirs(DATA_DIR, exist_ok=True)
    old = pd.read_csv(F_POWER) if os.path.exists(F_POWER) else None
    end_all = datetime.now(timezone.utc)
    frames = []
    for name, p in zones.items():
        start = pd.Timestamp(POWER_FIRST)
        if old is not None:
            sub = old[old["zone"] == name]
            if len(sub):
                start = pd.Timestamp(sub["date"].max()) + pd.Timedelta(days=1)
        for year in range(start.year, end_all.year + 1):
            s = max(start, pd.Timestamp(year=year, month=1, day=1))
            e = min(pd.Timestamp(end_all.date()), pd.Timestamp(year=year, month=12, day=31))
            if s > e:
                continue
            print(f"POWER {name} {s.date()} -> {e.date()}")
            try:
                df = get_power(p["lat"], p["lon"], POWER_PARAMS,
                               s.strftime("%Y%m%d"), e.strftime("%Y%m%d"))
            except Exception as ex:
                print("  skipped:", ex)
                continue
            df = df.rename_axis("date").reset_index()
            df["zone"] = name
            frames.append(df)
            time.sleep(1)
    if frames:
        new = pd.concat(frames, ignore_index=True)
        new["date"] = pd.to_datetime(new["date"]).dt.strftime("%Y-%m-%d")
        out = new if old is None else pd.concat([old, new], ignore_index=True)
        out = out.dropna(subset=["T2M"]).drop_duplicates(["date", "zone"]).sort_values(["zone", "date"])
        save_csv(out, F_POWER)
        print("POWER saved:", len(out), "rows")
    else:
        print("POWER already up to date")


# MODIS NDVI (vegetation)

def modis_get(path, params, tries=4, backoff=5, timeout=(15, 90)):
    return http_json(f"{MODIS}/{path}", params, tries=tries, headers=MODIS_HEADERS,
                     backoff=backoff, timeout=timeout)


def get_ndvi(lat, lon):
    d = modis_get("MOD13Q1/dates", {"latitude": lat, "longitude": lon}, tries=1, timeout=(5, 10))
    if d is None:
        return None
    latest = d["dates"][-1]
    s = modis_get("MOD13Q1/subset", {
        "latitude": lat, "longitude": lon,
        "band": "250m_16_days_NDVI",
        "startDate": latest["modis_date"], "endDate": latest["modis_date"],
        "kmAboveBelow": 1, "kmLeftRight": 1,
    }, tries=1, timeout=(5, 15))
    if s is None:
        return None
    pixels = np.array(s["subset"][0]["data"], dtype=float)
    pixels[pixels < -2000] = np.nan
    if np.isnan(pixels).all():
        return None
    return {"date": latest["calendar_date"],
            "ndvi": round(float(np.nanmean(pixels) * 0.0001), 3)}


def _save_ndvi_rows(rows):
    if not rows:
        return
    cur = pd.read_csv(F_NDVI) if os.path.exists(F_NDVI) else None
    new = pd.DataFrame(rows)
    out = new if cur is None else pd.concat([cur, new], ignore_index=True)
    out = out.drop_duplicates(["date", "zone"]).sort_values(["zone", "date"])
    save_csv(out, F_NDVI)
    print(f"    saved ({len(out)} rows total)")


def build_ndvi():
    """Patient mode: MODIS server is often overloaded, so wait and retry a lot.
    Saves every 20 requests and fills any gaps on re-run."""
    os.makedirs(DATA_DIR, exist_ok=True)
    for name, p in zones.items():
        d = modis_get("MOD13Q1/dates", {"latitude": p["lat"], "longitude": p["lon"]},
                      tries=5, backoff=20)
        if d is None:
            print(f"NDVI {name}: MODIS server not answering, try again later")
            return
        dates = [x for x in d["dates"] if x["calendar_date"] >= NDVI_FIRST]
        cur = pd.read_csv(F_NDVI) if os.path.exists(F_NDVI) else None
        if cur is not None:
            have = set(cur.loc[cur["zone"] == name, "date"])
            dates = [x for x in dates if x["calendar_date"] not in have]
        print(f"NDVI {name}: {len(dates)} composites to fetch")

        rows, fails = [], 0
        for n, i in enumerate(range(0, len(dates), NDVI_CHUNK), start=1):
            chunk = dates[i:i + NDVI_CHUNK]
            s_ = modis_get("MOD13Q1/subset", {
                "latitude": p["lat"], "longitude": p["lon"],
                "band": "250m_16_days_NDVI",
                "startDate": chunk[0]["modis_date"], "endDate": chunk[-1]["modis_date"],
                "kmAboveBelow": 1, "kmLeftRight": 1,
            }, tries=5, backoff=20)               
            if s_ is None:
                fails += 1
                print(f"  chunk at {chunk[0]['calendar_date']} failed ({fails}/5 in a row)")
                if fails >= 5:
                    _save_ndvi_rows(rows)
                    print("  MODIS server is down for now. Progress saved. Re-run later to continue.")
                    return
                continue
            fails = 0
            for item in s_["subset"]:
                px = np.array(item["data"], dtype=float)
                px[px < -2000] = np.nan
                if np.isnan(px).all():
                    continue
                rows.append({"date": item["calendar_date"], "zone": name,
                             "ndvi": round(float(np.nanmean(px) * 0.0001), 4)})
            if n % 20 == 0:
                print(f"  {name}: {min(i + NDVI_CHUNK, len(dates))}/{len(dates)} (up to {chunk[-1]['calendar_date']})")
                _save_ndvi_rows(rows)
                rows = []
            time.sleep(2)                       
        _save_ndvi_rows(rows)
        print(f"NDVI {name}: done")



# SRTM elevation

def build_elevation(half_width_deg=0.2, n=9):
    """Point elevation + min/max/mean over a ~45 km square around each zone."""
    os.makedirs(DATA_DIR, exist_ok=True)
    offsets = np.linspace(-half_width_deg, half_width_deg, n)
    out = {}
    for name, p in zones.items():
        pts = [(p["lat"] + dy, p["lon"] + dx) for dy in offsets for dx in offsets]
        locs = "|".join(f"{la:.5f},{lo:.5f}" for la, lo in pts)
        d = http_json("https://api.opentopodata.org/v1/srtm30m", {"locations": locs}, tries=4)
        if d is None or d.get("status") != "OK":
            print("elevation failed for", name)
            continue
        vals = [r["elevation"] for r in d["results"] if r["elevation"] is not None]
        centre = d["results"][len(pts) // 2]["elevation"]
        out[name] = {
            "point_m": centre,
            "min_m": float(np.min(vals)), "max_m": float(np.max(vals)),
            "mean_m": round(float(np.mean(vals)), 1),
            "area": f"~{int(half_width_deg * 2 * 111)} km square around the point",
            "source": "SRTM 30 m (via OpenTopoData)",
        }
        print("elevation", name, out[name]["point_m"], "m")
        time.sleep(1.2)                     
    if out:
        with open(F_ELEV, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print("elevation saved")


# GPM IMERG rainfall 
def _open_precip(path):
    """Monthly IMERG files keep data in group 'Grid'; daily files keep it at the top level."""
    import xarray as xr
    last_err = None
    for group in ("Grid", None):
        try:
            if group:
                d = xr.open_dataset(path, engine="h5netcdf", group=group)
            else:
                d = xr.open_dataset(path, engine="h5netcdf")
            if "precipitation" in d.variables:
                return d
            d.close()
        except Exception as e:
            last_err = e
    raise RuntimeError(f"no precipitation variable found ({type(last_err).__name__}: {last_err})")


def _extract_points(path, value_col):
    rows = []
    with _open_precip(path) as d:
        date = str(d["time"].values[0])[:10]
        for name, p in zones.items():
            v = d["precipitation"].sel(lon=p["lon"], lat=p["lat"], method="nearest")
            rows.append({"date": date, "zone": name,
                         value_col: float(v.values.squeeze()),
                         "cell_lat": float(v["lat"]), "cell_lon": float(v["lon"])})
    return rows


_logged_in = False


def _earth_login():
    global _logged_in
    if _logged_in:
        return
    import earthaccess
    auth = earthaccess.login(persist=True)      
    if not getattr(auth, "authenticated", True):
        raise RuntimeError("Earthdata login failed")
    _logged_in = True


def _download_batch(granules, tag, tries=3, limit=240):
    """Download with a watchdog. Temp files go to the system temp folder (outside OneDrive).
    If a batch stalls for `limit` seconds it is abandoned and retried in a fresh folder."""
    import earthaccess
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
    base = os.path.join(tempfile.gettempdir(), "rainguard_tmp")
    folders = []
    for attempt in range(1, tries + 1):
        folder = os.path.join(base, f"{tag}_{int(time.time())}_{attempt}")
        folders.append(folder)
        ex = ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(earthaccess.download, granules, folder, threads=4, show_progress=False)
        try:
            files = fut.result(timeout=limit)
            ex.shutdown(wait=False)
            return files, folders
        except FutTimeout:
            print(f"  batch stalled for {limit}s, retrying ({attempt}/{tries})", flush=True)
        except Exception as e:
            print(f"  download error: {type(e).__name__}: {str(e)[:150]} (attempt {attempt}/{tries})", flush=True)
        ex.shutdown(wait=False)
        time.sleep(5)
    return [], folders


def _fetch_rain(short_name, start, end, value_col, batch=25):
    """Yields (DataFrame for this batch, done, total). Stops if downloads keep failing."""
    import earthaccess
    _earth_login()
    results = earthaccess.search_data(short_name=short_name, version="07",
                                      temporal=(start, end), count=-1)
    print(f"{short_name}: {len(results)} granules from {start} to {end}")
    empty_in_a_row = 0
    for i in range(0, len(results), batch):
        print(f"  downloading files {i + 1}-{min(i + batch, len(results))} of {len(results)} ...", flush=True)
        files, folders = _download_batch(results[i:i + batch], short_name)
        rows, skipped, first_err = [], 0, None
        for f in files:
            try:
                rows += _extract_points(str(f), value_col)
            except Exception as e:
                skipped += 1
                first_err = first_err or f"{type(e).__name__}: {str(e)[:200]}"
        if skipped:
            print(f"  skipped {skipped} files. First error: {first_err}")
        for fo in folders:
            shutil.rmtree(fo, ignore_errors=True)
        if not rows:
            empty_in_a_row += 1
            print(f"  batch starting at {i} gave no data ({empty_in_a_row}/3)")
            if empty_in_a_row >= 3:
                print("  Stopping: downloads keep failing. Read the messages above, then re-run.")
                return
            continue
        empty_in_a_row = 0
        yield pd.DataFrame(rows), min(i + batch, len(results)), len(results)


def _build_rain_product(short_name, first, out_csv, value_col, post=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    old = pd.read_csv(out_csv) if os.path.exists(out_csv) else None
    start = first
    if old is not None and len(old):
        start = (pd.Timestamp(old["date"].max()) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    end = utc_today()
    if start > end:
        print(short_name, "already up to date")
        return
    for df, done, total in _fetch_rain(short_name, start, end, value_col):
        if df.empty:
            continue
        cur = df if old is None else pd.concat([old, df], ignore_index=True)
        cur = cur.drop_duplicates(["date", "zone"]).sort_values(["zone", "date"])
        if post:
            cur = post(cur)
        save_csv(cur, out_csv)                       
        print(f"{short_name}: {done}/{total} saved through {cur['date'].max()}")


def _monthly_post(df):
    df = df.copy()
    days = pd.to_datetime(df["date"]).dt.days_in_month
    df["rain_mm_month"] = df["precip_mm_hr"] * days * 24      
    return df


def build_rain():

    _build_rain_product("GPM_3IMERGDF", RAIN_DAILY_FIRST, F_RAIN_DAILY, "rain_mm_day")
    
    _build_rain_product("GPM_3IMERGM", RAIN_MONTHLY_FIRST, F_RAIN_MONTHLY,
                        "precip_mm_hr", post=_monthly_post)
    if os.path.exists(F_RAIN_DAILY):
        last_final = pd.read_csv(F_RAIN_DAILY)["date"].max()
        start = (pd.Timestamp(last_final) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        if start <= utc_today():
            frames = [df for df, _, _ in _fetch_rain("GPM_3IMERGDL", start, utc_today(), "rain_mm_day")]
            if frames:
                last = pd.concat(frames, ignore_index=True)
                last = last.drop_duplicates(["date", "zone"]).sort_values(["zone", "date"])
                save_csv(last, F_RAIN_LATE)
                print("late run saved through", last["date"].max())


def build_all():
    steps = [build_elevation, build_power] + ([build_ndvi] if ENABLE_NDVI else []) + [build_rain]
    for step in steps:
        try:
            step()
        except Exception as e:
            print(f"{step.__name__} failed: {type(e).__name__}: {e}")


# API

POWER_TTL = 60 * 60          # re-check NASA POWER at most every hour
NDVI_TTL = 12 * 60 * 60      # re-check MODIS at most every 12 hours
_cache = {}                
_tables = {}                

FAIL_TTL = 5 * 60            # after a failed live call, do not retry for 5 minutes
_failed = {}


def cached(key, ttl, fetch):
    hit = _cache.get(key)
    if hit and time.time() - hit["at"] < ttl:
        return hit["data"]
    if time.time() - _failed.get(key, 0) < FAIL_TTL:      # recently failed: answer fast
        return hit["data"] if hit else None
    try:
        data = fetch()
    except Exception:
        data = None
    if data is None:
        _failed[key] = time.time()
        return hit["data"] if hit else None               # serve the old value if NASA is down
    _failed.pop(key, None)
    _cache[key] = {"at": time.time(), "data": data}
    return data


def _read_csv(path):
    if not os.path.exists(path):
        return None
    m = os.path.getmtime(path)
    hit = _tables.get(path)
    if hit and hit[0] == m:
        return hit[1]
    df = pd.read_csv(path)
    _tables[path] = (m, df)
    return df


def _rain_table():
    final = _read_csv(F_RAIN_DAILY)
    if final is None:
        return None
    final = final[["date", "zone", "rain_mm_day"]].assign(source="final")
    late = _read_csv(F_RAIN_LATE)
    if late is not None and len(late):
        late = late[["date", "zone", "rain_mm_day"]].assign(source="late")
        late = late[late["date"] > final["date"].max()]
        final = pd.concat([final, late], ignore_index=True)
    return final.sort_values(["zone", "date"])


def _table(name):
    if name == "power":
        return _read_csv(F_POWER)
    if name == "ndvi":
        return _read_csv(F_NDVI)
    if name == "rain":
        return _rain_table()
    return None


def check_zone(zone):
    if zone not in zones:
        raise HTTPException(404, f"Unknown zone. Choose from: {list(zones)}")
    return zones[zone]


def latest_weather(zone):
    p = check_zone(zone)

    def fetch():
        w = get_weather_soil(p["lat"], p["lon"])
        row = w.iloc[-1]
        return {"date": str(w.index[-1].date()), **row.to_dict()}

    data = cached(("power", zone), POWER_TTL, fetch)
    if data is None:                                     # fall back to the saved history
        t = _table("power")
        if t is not None:
            sub = t[t["zone"] == zone].dropna(subset=["T2M", "RH2M", "GWETTOP", "GWETROOT", "GWETPROF"])
            if len(sub):
                data = sub.iloc[-1].to_dict()
    if data is None:
        raise HTTPException(503, "NASA POWER is unavailable and no saved data. Run: python main.py build power")
    return data


def latest_ndvi(zone):
    p = check_zone(zone)
    t = _table("ndvi")                      
    if t is not None:
        sub = t[t["zone"] == zone].sort_values("date")
        if len(sub):
            r = sub.iloc[-1]
            out = {"date": r["date"], "ndvi": round(float(r["ndvi"]), 3)}
            if "evi" in sub.columns and pd.notna(r["evi"]):
                out["evi"] = round(float(r["evi"]), 3)
            return out
    data = cached(("ndvi", zone), NDVI_TTL, lambda: get_ndvi(p["lat"], p["lon"]))   # no file: try live
    if data is None:
        raise HTTPException(503, "No vegetation data. Add data/ndvi.csv (see convert scripts).")
    return data


def latest_rain(zone):
    check_zone(zone)
    t = _table("rain")
    if t is None:
        raise HTTPException(503, f"No rainfall data found at {os.path.abspath(F_RAIN_DAILY)}. Run: python main.py build rain")
    sub = t[t["zone"] == zone]
    if sub.empty:
        raise HTTPException(503, "No rainfall rows for this zone yet")
    last = sub.iloc[-1]
    end = pd.Timestamp(last["date"])
    d = pd.to_datetime(sub["date"])
    return {
        "zone": zone, "date": last["date"],
        "value": round(float(last["rain_mm_day"]), 2), "unit": "mm/day",
        "source": last["source"],       
        "age_days": int((pd.Timestamp(utc_today()) - end).days),   
        "last_7_days_mm": round(float(sub.loc[d > end - pd.Timedelta(days=7), "rain_mm_day"].sum()), 1),
        "last_30_days_mm": round(float(sub.loc[d > end - pd.Timedelta(days=30), "rain_mm_day"].sum()), 1),
    }


def elevation_info(zone):
    check_zone(zone)
    if not os.path.exists(F_ELEV):
        raise HTTPException(503, f"No elevation data found at {os.path.abspath(F_ELEV)}. Run: python main.py build elevation")
    with open(F_ELEV, encoding="utf-8") as f:
        data = json.load(f)
    if zone not in data:
        raise HTTPException(503, "No elevation for this zone yet")
    return {"zone": zone, "unit": "m", **data[zone]}


@asynccontextmanager
async def lifespan(app):
    if os.getenv("AUTO_REFRESH") == "1":
        def loop():
            while True:
                try:
                    build_all()
                except Exception as e:
                    print("refresh failed:", e)
                time.sleep(24 * 60 * 60)
        threading.Thread(target=loop, daemon=True).start()
    yield


app = FastAPI(title="RainGuard Ethiopia", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware  
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/")
def home():
    endpoints = ["/zones", "/temperature/{zone}", "/humidity/{zone}",
                 "/soil-moisture/{zone}", "/rainfall/{zone}"]
    if ENABLE_NDVI:
        endpoints.append("/vegetation/{zone}")
    endpoints += ["/elevation/{zone}", "/summary/{zone}", "/history/{zone}?variable=&start=&end="]
    return {"service": "RainGuard Ethiopia", "docs": "/docs", "endpoints": endpoints}


@app.get("/zones")
def list_zones():
    return list(zones)


@app.get("/temperature/{zone}")
def temperature(zone: str):
    d = latest_weather(zone)
    out = {"zone": zone, "date": d["date"], "value": round(d["T2M"], 2), "unit": "°C"}
    if pd.notna(d.get("T2M_MAX")):
        out["max"] = round(d["T2M_MAX"], 2)
    if pd.notna(d.get("T2M_MIN")):
        out["min"] = round(d["T2M_MIN"], 2)
    return out


@app.get("/humidity/{zone}")
def humidity(zone: str):
    d = latest_weather(zone)
    return {"zone": zone, "date": d["date"], "value": round(d["RH2M"], 2), "unit": "%"}


@app.get("/soil-moisture/{zone}")
def soil_moisture(zone: str):
    d = latest_weather(zone)
    return {"zone": zone, "date": d["date"], "unit": "0-1",
            "top": round(d["GWETTOP"], 3), "root": round(d["GWETROOT"], 3),
            "profile": round(d["GWETPROF"], 3),
            "note": "Modelled soil wetness from NASA POWER, not a satellite measurement"}


@app.get("/rainfall/{zone}")
def rainfall(zone: str):
    return latest_rain(zone)


@app.get("/vegetation/{zone}", include_in_schema=ENABLE_NDVI)
def vegetation(zone: str):
    if not ENABLE_NDVI:
        raise HTTPException(404, "Vegetation (NDVI) is not enabled yet")
    return {"zone": zone, **latest_ndvi(zone)}


@app.get("/elevation/{zone}")
def elevation(zone: str):
    return elevation_info(zone)


@app.get("/summary/{zone}")
def summary(zone: str):
    check_zone(zone)
    out = {"zone": zone}
    parts = [("temperature", temperature), ("humidity", humidity),
             ("soil_moisture", soil_moisture), ("rainfall", rainfall)]
    if ENABLE_NDVI:
        parts.append(("vegetation", vegetation))
    parts.append(("elevation", elevation))
    for key, fn in parts:
        try:
            out[key] = fn(zone)
        except HTTPException as e:
            out[key] = {"error": e.detail}
    return out


HISTORY = {
    "temperature":   ("power", ["T2M", "T2M_MAX", "T2M_MIN"]),
    "humidity":      ("power", ["RH2M"]),
    "soil_moisture": ("power", ["GWETTOP", "GWETROOT", "GWETPROF"]),
    "rainfall":      ("rain",  ["rain_mm_day", "source"]),
    "vegetation":    ("ndvi",  ["ndvi", "evi"]),
}
if not ENABLE_NDVI:
    HISTORY.pop("vegetation")


@app.get("/history/{zone}")
def history(zone: str, variable: str, start: str = "2000-01-01",
            end: str = "", limit: int = 5000):
    check_zone(zone)
    if variable not in HISTORY:
        raise HTTPException(400, f"variable must be one of {list(HISTORY)}")
    table_name, cols = HISTORY[variable]
    t = _table(table_name)
    if t is None:
        raise HTTPException(503, f"No saved data for {variable} yet. Run: python main.py build")
    end = end or utc_today()
    sub = t[(t["zone"] == zone) & (t["date"] >= start) & (t["date"] <= end)]
    sub = sub[["date"] + [c for c in cols if c in t.columns]].tail(max(1, min(limit, 20000)))
    sub = sub.astype(object).where(sub.notna(), None)
    return {"zone": zone, "variable": variable, "count": len(sub),
            "data": sub.to_dict(orient="records")}



if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] != "build":
        print(__doc__)
        sys.exit(0)
    what = args[1] if len(args) > 1 else "all"
    steps = {"rain": build_rain, "power": build_power, "ndvi": build_ndvi,
             "elevation": build_elevation, "all": build_all}
    if what not in steps:
        print("unknown step; choose from:", list(steps))
        sys.exit(1)
    steps[what]()
