"""
Tests for network_geometry.parse_network_geometry - plain stdlib XML parsing
of a SUMO .net.xml file's lane shapes, with no sumolib/SUMO install needed.
"""

import os
import time

import pytest

import network_geometry
from network_geometry import NetworkGeometryError, parse_network_geometry

REAL_NET_FILE = os.path.join('BolognaScenario', 'acosta_buslanes.net.xml')

MINIMAL_NET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<net version="1.3">
    <location netOffset="0.00,0.00" convBoundary="0.00,0.00,100.00,50.00" origBoundary="0.00,0.00,100.00,50.00" projParameter="!"/>
    <edge id="1" from="a" to="b" priority="-1">
        <lane id="1_0" index="0" speed="13.89" length="10.00" shape="0.00,0.00 10.00,0.00"/>
    </edge>
</net>
"""


@pytest.fixture(autouse=True)
def clear_cache():
    # The module-level cache is keyed by path; tmp_path gives each test a
    # fresh unique path already, but clear it anyway so test order/reruns
    # can't leak state between tests.
    network_geometry._cache.clear()
    yield
    network_geometry._cache.clear()


class TestParseNetworkGeometry:
    def test_parses_real_network_file(self):
        geometry = parse_network_geometry(REAL_NET_FILE)
        # Known convBoundary from BolognaScenario/acosta_buslanes.net.xml.
        assert geometry.bounds == pytest.approx((0.00, 0.00, 1817.58, 1350.19))
        assert len(geometry.segments) > 100
        for segment in geometry.segments:
            assert len(segment) >= 2
            for x, y in segment:
                assert isinstance(x, float)
                assert isinstance(y, float)

    def test_missing_file_raises_network_geometry_error(self, tmp_path):
        missing_path = str(tmp_path / 'does_not_exist.net.xml')
        with pytest.raises(NetworkGeometryError):
            parse_network_geometry(missing_path)

    def test_malformed_xml_raises_network_geometry_error(self, tmp_path):
        bad_path = tmp_path / 'malformed.net.xml'
        bad_path.write_text('<net><location convBoundary="0,0,1,1"/><edge>')
        with pytest.raises(NetworkGeometryError):
            parse_network_geometry(str(bad_path))

    def test_missing_location_tag_raises_network_geometry_error(self, tmp_path):
        no_location_path = tmp_path / 'no_location.net.xml'
        no_location_path.write_text('<net><edge id="1"><lane id="1_0" shape="0,0 1,1"/></edge></net>')
        with pytest.raises(NetworkGeometryError):
            parse_network_geometry(str(no_location_path))

    def test_malformed_conv_boundary_raises_network_geometry_error(self, tmp_path):
        # Well-formed XML, but convBoundary has 3 values instead of 4 - a
        # raw ValueError from tuple-unpacking must not escape uncaught.
        bad_path = tmp_path / 'bad_boundary.net.xml'
        bad_path.write_text(
            '<net><location convBoundary="0,0,100"/>'
            '<edge id="1"><lane id="1_0" shape="0,0 1,1"/></edge></net>'
        )
        with pytest.raises(NetworkGeometryError):
            parse_network_geometry(str(bad_path))

    def test_malformed_lane_shape_raises_network_geometry_error(self, tmp_path):
        # A shape token with no comma - a raw ValueError from pair.split(',')
        # unpacking must not escape uncaught.
        bad_path = tmp_path / 'bad_shape.net.xml'
        bad_path.write_text(
            '<net><location convBoundary="0,0,100,100"/>'
            '<edge id="1"><lane id="1_0" shape="not-a-coordinate 1,1"/></edge></net>'
        )
        with pytest.raises(NetworkGeometryError):
            parse_network_geometry(str(bad_path))

    def test_parses_minimal_network_correctly(self, tmp_path):
        net_path = tmp_path / 'minimal.net.xml'
        net_path.write_text(MINIMAL_NET_XML)
        geometry = parse_network_geometry(str(net_path))
        assert geometry.bounds == pytest.approx((0.0, 0.0, 100.0, 50.0))
        assert geometry.segments == [[(0.0, 0.0), (10.0, 0.0)]]


class TestCache:
    def test_second_call_returns_same_object_for_unchanged_file(self, tmp_path):
        net_path = tmp_path / 'cached.net.xml'
        net_path.write_text(MINIMAL_NET_XML)
        first = parse_network_geometry(str(net_path))
        second = parse_network_geometry(str(net_path))
        assert first is second

    def test_recomputes_after_file_mtime_changes(self, tmp_path):
        net_path = tmp_path / 'changing.net.xml'
        net_path.write_text(MINIMAL_NET_XML)
        first = parse_network_geometry(str(net_path))
        assert len(first.segments) == 1

        changed_xml = MINIMAL_NET_XML.replace(
            '</net>',
            '<edge id="2"><lane id="2_0" shape="20.00,20.00 30.00,30.00"/></edge></net>',
        )
        # Ensure the filesystem mtime actually advances - some filesystems
        # have coarse (1s) mtime resolution.
        time.sleep(1.1)
        net_path.write_text(changed_xml)

        second = parse_network_geometry(str(net_path))
        assert second is not first
        assert len(second.segments) == 2
