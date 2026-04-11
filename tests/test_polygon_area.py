"""GeoJSON 多边形面积（公顷）。"""

from app.geo.polygon_area import polygon_area_hectares_wgs84


def test_polygon_area_small_square_near_beijing() -> None:
    geom = {
        "type": "Polygon",
        "coordinates": [[[116.3, 39.9], [116.301, 39.9], [116.301, 39.901], [116.3, 39.901], [116.3, 39.9]]],
    }
    ha = polygon_area_hectares_wgs84(geom)
    assert 0.8 < ha < 1.4


def test_polygon_area_non_polygon_zero() -> None:
    assert polygon_area_hectares_wgs84({"type": "LineString", "coordinates": [[0, 0], [1, 1]]}) == 0.0
