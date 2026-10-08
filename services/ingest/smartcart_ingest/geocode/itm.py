"""Israeli Transverse Mercator (ITM, EPSG:2039) to WGS 84 (EPSG:4326), standard library only.

CBS and other Israeli sources publish coordinates in ITM metres (east X, north Y). ITM is a
transverse Mercator on GRS 80 over the "Israel 1993" datum, so converting takes two steps:

1. the inverse transverse Mercator projection (Krueger series, accurate to well under a
   millimetre inside Israel), giving latitude and longitude on the Israel 1993 ellipsoid;
2. the seven-parameter Helmert transformation Israel 1993 to WGS 84 (EPSG:1086 as PROJ applies
   it to EPSG:2039), through geocentric coordinates.

The tests compare the result with pyproj on a spread of points (to about a decimetre) and with
known places. Nothing here guesses: a point that converts outside Israel's bounding box is
rejected by the caller, not clamped.
"""

from __future__ import annotations

from math import asin, atan, atan2, atanh, cos, cosh, degrees, radians, sin, sinh, sqrt, tanh

# GRS 80
_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
# ITM projection parameters (EPSG:2039)
_LAT0 = radians(31 + 44 / 60 + 3.817 / 3600)
_LON0 = radians(35 + 12 / 60 + 16.261 / 3600)
_K0 = 1.0000067
_FE = 219529.584
_FN = 626907.390
# Israel 1993 -> WGS 84, coordinate-frame rotation convention (EPSG:9607), metres, arc-seconds, ppm
_TX, _TY, _TZ = 24.0024, 17.1032, 17.8444
_RX, _RY, _RZ = (radians(v / 3600) for v in (0.33077, 1.85269, -1.66969))
_DS = -5.4248e-6
# WGS 84
_WA = 6378137.0
_WF = 1 / 298.257223563
_WE2 = _WF * (2 - _WF)

# Israel's extent, used by callers to reject nonsense (WGS 84 degrees)
ISRAEL_LAT = (29.0, 33.5)
ISRAEL_LON = (34.0, 36.0)


def _series() -> tuple[float, tuple[float, ...], tuple[float, ...]]:
    n = _F / (2 - _F)
    big_a = _A / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    alpha = (
        n / 2 - 2 * n**2 / 3 + 5 * n**3 / 16,
        13 * n**2 / 48 - 3 * n**3 / 5,
        61 * n**3 / 240,
    )
    beta = (
        n / 2 - 2 * n**2 / 3 + 37 * n**3 / 96,
        n**2 / 48 + n**3 / 15,
        17 * n**3 / 480,
    )
    return big_a, alpha, beta


_BIG_A, _ALPHA, _BETA = _series()
_E = sqrt(_E2)


def _conformal_latitude(lat: float) -> float:
    return atan(sinh(atanh(sin(lat)) - _E * atanh(_E * sin(lat))))


# Meridian distance of the projection's origin latitude (the dlon = 0 case of the forward series)
_XI0 = _conformal_latitude(_LAT0)
_M0 = _BIG_A * (_XI0 + sum(a * sin(2 * (j + 1) * _XI0) for j, a in enumerate(_ALPHA)))


def itm_to_israel1993(east: float, north: float) -> tuple[float, float]:
    """Inverse transverse Mercator: ITM metres to (lat, lon) degrees on the Israel 1993 datum."""
    xi = (north - _FN + _K0 * _M0) / (_K0 * _BIG_A)
    eta = (east - _FE) / (_K0 * _BIG_A)
    xi_p = xi - sum(
        b * sin(2 * (j + 1) * xi) * cosh(2 * (j + 1) * eta) for j, b in enumerate(_BETA)
    )
    eta_p = eta - sum(
        b * cos(2 * (j + 1) * xi) * sinh(2 * (j + 1) * eta) for j, b in enumerate(_BETA)
    )
    chi = asin(sin(xi_p) / cosh(eta_p))
    lon = _LON0 + atan2(sinh(eta_p), cos(xi_p))
    lat = chi
    for _ in range(10):  # geodetic from conformal latitude
        lat = asin(tanh(atanh(sin(chi)) + _E * atanh(_E * sin(lat))))
    return degrees(lat), degrees(lon)


def _to_geocentric(lat: float, lon: float, a: float, e2: float) -> tuple[float, float, float]:
    nu = a / sqrt(1 - e2 * sin(lat) ** 2)
    return (
        nu * cos(lat) * cos(lon),
        nu * cos(lat) * sin(lon),
        nu * (1 - e2) * sin(lat),
    )


def _from_geocentric(x: float, y: float, z: float, a: float, e2: float) -> tuple[float, float]:
    p = sqrt(x * x + y * y)
    lat = atan2(z, p * (1 - e2))
    for _ in range(8):
        nu = a / sqrt(1 - e2 * sin(lat) ** 2)
        lat = atan2(z + e2 * nu * sin(lat), p)
    return lat, atan2(y, x)


def israel1993_to_wgs84(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """Seven-parameter Helmert from Israel 1993 (GRS 80) to WGS 84, heights taken as zero."""
    x, y, z = _to_geocentric(radians(lat_deg), radians(lon_deg), _A, _E2)
    s = 1 + _DS
    x2 = _TX + s * (x + _RZ * y - _RY * z)
    y2 = _TY + s * (-_RZ * x + y + _RX * z)
    z2 = _TZ + s * (_RY * x - _RX * y + z)
    lat, lon = _from_geocentric(x2, y2, z2, _WA, _WE2)
    return degrees(lat), degrees(lon)


def itm_to_wgs84(east: float, north: float) -> tuple[float, float]:
    """ITM (EPSG:2039) metres to WGS 84 ``(lat, lon)`` degrees."""
    lat, lon = itm_to_israel1993(east, north)
    return israel1993_to_wgs84(lat, lon)


def in_israel(lat: float, lon: float) -> bool:
    return ISRAEL_LAT[0] <= lat <= ISRAEL_LAT[1] and ISRAEL_LON[0] <= lon <= ISRAEL_LON[1]


__all__ = ["in_israel", "israel1993_to_wgs84", "itm_to_israel1993", "itm_to_wgs84"]
