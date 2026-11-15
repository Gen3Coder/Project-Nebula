"""Vapor pressure deficit and FAO-56 Penman-Monteith reference evapotranspiration."""
import numpy as np


def sat_vapor_pressure(t_c):
    """Saturation vapor pressure (kPa) at air temperature t_c (deg C)."""
    return 0.6108 * np.exp(17.27 * t_c / (t_c + 237.3))


def extraterrestrial_radiation(doy, lat_deg):
    """Ra in MJ m-2 day-1 (FAO-56 eq. 21)."""
    lat = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(lat) * np.tan(delta), -1, 1))
    gsc = 0.0820
    return (24 * 60 / np.pi) * gsc * dr * (
        ws * np.sin(lat) * np.sin(delta) + np.cos(lat) * np.cos(delta) * np.sin(ws)
    )


def vpd_and_et0(tmean, tmax, tmin, rh, wind10, rs_mj, doy, lat_deg, elev_m):
    """
    Returns (VPD in kPa, ET0 in mm/day).
    Inputs are daily values (numpy arrays). rs_mj = solar radiation in MJ m-2 day-1.
    Wind is converted from 10 m to 2 m height. Soil heat flux is taken as 0 (daily step).
    """
    es_mean = (sat_vapor_pressure(tmax) + sat_vapor_pressure(tmin)) / 2
    ea = np.clip(rh, 0, 100) / 100 * es_mean
    vpd = np.clip(es_mean - ea, 0, None)

    pressure = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    slope = 4098 * sat_vapor_pressure(tmean) / (tmean + 237.3) ** 2
    u2 = wind10 * 4.87 / np.log(67.8 * 10 - 5.42)

    ra = extraterrestrial_radiation(doy, lat_deg)
    rso = (0.75 + 2e-5 * elev_m) * ra
    ratio = np.clip(rs_mj / rso, 0.3, 1.0)
    rns = 0.77 * rs_mj
    rnl = 4.903e-9 * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2) \
        * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * ratio - 0.35)
    rn = rns - rnl

    et0 = (0.408 * slope * rn + gamma * 900 / (tmean + 273) * u2 * (es_mean - ea)) / \
          (slope + gamma * (1 + 0.34 * u2))
    return vpd, np.clip(et0, 0, None)
