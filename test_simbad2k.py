"""
test_simbad2k.py - Integration tests for the simbad2k service.

These tests do not patch astroquery, so requests are actually sent across the network by
astroquery to retrieve results from the sources it pulls from.
"""
import pytest

import simbad2k


@pytest.fixture
def client():
    simbad2k.app.config['TESTING'] = True

    with simbad2k.app.test_client() as client:
        yield client

    simbad2k.cache.clear()


def test_index(client):
    response = client.get('/')
    assert b'This is simbad2k' in response.data


def test_sidereal(client):
    response = client.get('/m88?target_type=sidereal')
    assert response.is_json
    response_json = response.get_json()
    assert 'ra' in response_json
    assert 'dec' in response_json


def test_cached_sidereal_target_is_not_returned_when_non_sidereal_is_requested_next(client):
    # Get data for M88 which is a sidereal target, and specify the correct target type.
    sidereal_response = client.get('/m88?target_type=sidereal').get_json()
    assert 'ra' in sidereal_response
    assert 'dec' in sidereal_response
    # Get M88 again, only this time set the wrong target type. The cached result from the previous run
    # should not be returned, we should get a different response.
    non_sidereal_response = client.get('/m88?target_type=non_sidereal').get_json()
    assert 'ra' not in non_sidereal_response
    assert 'dec' not in non_sidereal_response


def test_cached_response_is_not_returned_for_different_scheme_with_same_name(client):
    mpc_comet_response = client.get('/29P?target_type=non_sidereal&scheme=mpc_comet').get_json()
    mpc_minor_planet_response = client.get('/29P?target_type=non_sidereal&scheme=mpc_minor_planet').get_json()
    assert mpc_comet_response != mpc_minor_planet_response


def test_successfully_retrieved_result_is_cached(client):
    cache_key = simbad2k.generate_cache_key('m88', '', 'sidereal')
    assert simbad2k.cache.get(cache_key) is None
    client.get('/m88?target_type=sidereal').get_json()
    assert simbad2k.cache.get(cache_key) is not None


def test_mpc_result_field_as_null_does_not_crash(client):
    response = client.get('/C/2019 E3?target_type=non_sidereal&scheme=mpc_comet')
    assert response.status_code == 200
