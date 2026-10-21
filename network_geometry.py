"""
Lightweight geometry extraction from a SUMO .net.xml file, for drawing a
road-network outline as a map backdrop. Plain stdlib XML parsing only - no
sumolib/SUMO install dependency.
"""

import os
import xml.etree.ElementTree as ET


class NetworkGeometryError(Exception):
    """Raised when a .net.xml file is missing, malformed, or has no usable geometry."""


class NetworkGeometry:
    """Parsed road-network geometry: plot bounds + one polyline per lane.

    bounds: (min_x, min_y, max_x, max_y), in the same coordinate space as
    uav_data waypoints.
    segments: list of polylines, each a list of (x, y) tuples.
    """

    def __init__(self, bounds, segments):
        self.bounds = bounds
        self.segments = segments


_cache = {}  # path -> (mtime, NetworkGeometry)


def _parse_shape(shape_attr):
    points = []
    for pair in shape_attr.split():
        x_str, y_str = pair.split(',')
        points.append((float(x_str), float(y_str)))
    return points


def parse_network_geometry(path):
    """Parse a SUMO .net.xml file into line segments + bounds for plotting.

    Cached by (path, mtime): a second call for an unchanged file returns the
    same NetworkGeometry object; a call after the file's mtime changes
    reparses it. Raises NetworkGeometryError for a missing/malformed file or
    one with no <location convBoundary=...> tag, rather than letting a raw
    OSError/ParseError surface.
    """
    if not os.path.exists(path):
        raise NetworkGeometryError(f"Network file {path} not found.")

    mtime = os.path.getmtime(path)
    cached = _cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise NetworkGeometryError(f"Network file {path} is not valid XML: {e}")

    root = tree.getroot()
    location = root.find('location')
    if location is None or 'convBoundary' not in location.attrib:
        raise NetworkGeometryError(
            f"Network file {path} has no <location convBoundary=...> tag."
        )

    min_x, min_y, max_x, max_y = (
        float(v) for v in location.attrib['convBoundary'].split(',')
    )

    segments = []
    for edge in root.iter('edge'):
        for lane in edge.findall('lane'):
            shape = lane.attrib.get('shape')
            if shape:
                segments.append(_parse_shape(shape))

    geometry = NetworkGeometry(bounds=(min_x, min_y, max_x, max_y), segments=segments)
    _cache[path] = (mtime, geometry)
    return geometry
