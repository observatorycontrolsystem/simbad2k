"""
test_simbad2k.py - Tests for the simbad2k service.
"""
import pytest
from astropy.table import Table
from astroquery.mpc import MPC
from astroquery.ipac.ned import Ned

from simbad2k import simbad2k


@pytest.fixture(autouse=True)
def client():
    simbad2k.app.config['TESTING'] = True

    with simbad2k.app.test_client() as client:
        yield client

    simbad2k.cache.clear()


@pytest.fixture
def mock_mpc_response():
    # Return an astroquery MPC response that has no results, where results can be added in the tests. The astroquery
    # MPC query returns a list of dicts, where each dict has a set of oribital elements. Each set
    # are elements for different points in time.
    return []


@pytest.fixture
def mock_ned_response():
    # Return an astroquery Ned response that has no results, where results can be added in the tests. The astroquery
    # Ned query returns an astropy.table.Table.
    table = Table(
        names=('RA(deg)', 'DEC(deg)'),
        dtype=('f8', 'f8')
    )
    return table


@pytest.fixture
def mock_simbad_response():
    # Return an astroquery Simbad response that has no results, where results can be added in the tests. The astroquery
    # Simbad query returns an astropy.table.Table
    table = Table(
        names=('RA', 'DEC', 'RA_d', 'DEC_d', 'PMRA', 'PMDEC', 'PLX_VALUE', 'MAIN_ID'),
        dtype=('S', 'S', 'f8', 'f8', 'f8', 'f8', 'f8', 'S')
    )
    return table


@pytest.fixture(autouse=True)
def mock_astroquery_query(monkeypatch, mock_mpc_response, mock_ned_response, mock_simbad_response):
    """Mock responses from all calls to astroquery"""

    class MPCMockResponse:
        def json(self):
            return mock_mpc_response

    def mock_mcp_query_objects_async(*args, **kwargs):
        return MPCMockResponse()

    def mock_ned_query_object(*args, **kwargs):
        return mock_ned_response

    class MockSimbad:
        def query_object(self, *args, **kwargs):
            return mock_simbad_response

    monkeypatch.setattr(MPC, 'query_objects_async', mock_mcp_query_objects_async)
    monkeypatch.setattr(Ned, 'query_object', mock_ned_query_object)
    monkeypatch.setattr(simbad2k.SimbadQuery, '_get_simbad_instance', MockSimbad)


@pytest.fixture
def m88_simbad_table_row():
    return {
        'RA': '12 31 59.216',
        'DEC': '+14 25 13.48',
        'RA_d': '187.996733',
        'DEC_d': '14.420411',
        'PMRA': None,
        'PMDEC': None,
        'PLX_VALUE': None,
        'MAIN_ID': 'M  88'
    }


@pytest.fixture
def asteroid_29p_mpc_data():
    return {
        'argument_of_perihelion': '63.27357',
        'ascending_node': '356.335861',
        'designation': None,
        'eccentricity': '0.0729591',
        'epoch': '2020-05-31.0',
        'epoch_jd': '2459000.5',
        'inclination': '6.08187',
        'mean_anomaly': '20.89746',
        'name': 'Amphitrite',
        'number': 29,
        'perihelion_date_jd': '2458913.91759',
        'perihelion_distance': '2.3684211',
        'semimajor_axis': '2.5548184',
    }


@pytest.fixture
def comet_29p_mpc_data():
    return {
        'argument_of_perihelion': '77.94036',
        'ascending_node': '311.2559917',
        'designation': 'P/0029P',
        'eccentricity': '0.0344595',
        'epoch': '2035-02-02.0',
        'epoch_jd': '2464360.5',
        'inclination': '9.30703',
        'mean_anomaly': '359.21269',
        'number': 29,
        'object_type': 'P',
        'packed_designation': '0029P',
        'perihelion_date': '2035-02-13.48209',
        'perihelion_date_jd': '2464371.98209',
        'perihelion_distance': '5.7080983',
        'semimajor_axis': '5.9118162'
    }


def test_index(client):
    response = client.get('/')
    assert b'This is simbad2k' in response.data


def test_sidereal_simbad_target(client, mock_simbad_response, m88_simbad_table_row):
    mock_simbad_response.add_row(m88_simbad_table_row)
    response = client.get('/m88?target_type=sidereal')
    assert response.is_json
    response_json = response.get_json()
    assert response_json['ra'] == m88_simbad_table_row['RA']
    assert response_json['dec'] == m88_simbad_table_row['DEC']
    assert response_json['name'] == m88_simbad_table_row['MAIN_ID']


def test_successfully_retrieved_result_is_cached(client, mock_simbad_response, m88_simbad_table_row):
    mock_simbad_response.add_row(m88_simbad_table_row)
    cache_key = simbad2k.generate_cache_key('m88', '', 'sidereal')
    assert simbad2k.cache.get(cache_key) is None
    client.get('/m88?target_type=sidereal').get_json()
    assert simbad2k.cache.get(cache_key) is not None


def test_cached_is_not_returned_when_wrong_target_type_is_set(client, mock_simbad_response, m88_simbad_table_row):
    mock_simbad_response.add_row(m88_simbad_table_row)
    # Get data for M88 which is a sidereal target, and specify the correct target type.
    sidereal_response = client.get('/m88?target_type=sidereal').get_json()
    assert 'ra' in sidereal_response
    assert 'dec' in sidereal_response
    # Get M88 again, only this time set the wrong target type. The cached result from the previous run
    # should not be returned, we should get a different response.
    non_sidereal_response = client.get('/m88?target_type=non_sidereal').get_json()
    assert 'ra' not in non_sidereal_response
    assert 'dec' not in non_sidereal_response


def test_cached_response_is_not_returned_for_different_scheme_with_same_name(client, mock_mpc_response, asteroid_29p_mpc_data, comet_29p_mpc_data):
    # First have the MPC return the comet response for object 29p
    mock_mpc_response.append(comet_29p_mpc_data)
    mpc_comet_response = client.get('/29P?target_type=non_sidereal&scheme=mpc_comet').get_json()
    # Then have it return the asteroid response for 29p
    mock_mpc_response.clear()
    mock_mpc_response.append(asteroid_29p_mpc_data)
    mpc_minor_planet_response = client.get('/29P?target_type=non_sidereal&scheme=mpc_minor_planet').get_json()
    # The first result that was cached should not be returned for the second query
    assert mpc_comet_response != mpc_minor_planet_response, 'Returned targets should not be the same'


def test_mpc_result_field_as_null_does_not_crash(client, mock_mpc_response, comet_29p_mpc_data):
    comet_29p_mpc_data['mean_anomaly'] = None
    comet_29p_mpc_data['semimajor_axis'] = None
    mock_mpc_response.append(comet_29p_mpc_data)
    response = client.get('/29P?target_type=non_sidereal&scheme=mpc_comet')
    assert response.status_code == 200
    assert response.get_json()['mean_anomaly'] is None
