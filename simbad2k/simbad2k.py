#!/usr/bin/env python
from datetime import datetime
import hashlib
import logging
from logging.config import dictConfig
import math
import os
import requests

from astroquery.exceptions import RemoteServiceError
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_caching import Cache
from lcogt_logging import LCOGTFormatter

config = {
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 60 * 60 * 60
}

dictConfig({
    'version': 1,
    'formatters': {'default': {
        '()': LCOGTFormatter,
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)
CORS(app)


class PlanetQuery(object):
    def __init__(self, query, scheme):
        self.query = query.lower()
        self.scheme = scheme

    def get_result(self):
        import json
        with open(os.path.join(os.path.dirname(__file__), 'planets.json'), 'r') as planets:
            p_json = json.loads(planets.read())
        return p_json.get(self.query)


class SimbadQuery(object):
    def __init__(self, query, scheme):
        self.simbad = self._get_simbad_instance()
        self.query = query
        self.scheme = scheme

    def _get_simbad_instance(self):
        from astroquery.simbad import Simbad
        # The imported `Simbad` is already an instance of the `SimbadClass`, but we need to create a new instance
        # of it so that we only add the votable fields once
        simbad = Simbad()
        simbad.add_votable_fields('pmra', 'pmdec', 'ra', 'dec', 'plx_value', 'main_id')
        return simbad

    def get_result(self):
        result = self.simbad.query_object(self.query)
        if result:
            ret_dict = {}
            for key in ['pmra', 'pmdec', 'ra', 'dec', 'plx_value', 'main_id']:
                if str(result[key][0]) not in ['--', '']:
                    ret_dict[key.lower()] = result[key][0]
            if ret_dict.get('main_id'):
                ret_dict['name'] = ret_dict['main_id']
                del ret_dict['main_id']
            # Earlier versions of Simbad returned both sexagesimal and decimal coordinates. We return ra_d and dec_d
            # to maintain backwards compatibility with the old API.
            ret_dict['ra_d'] = ret_dict['ra']
            ret_dict['dec_d'] = ret_dict['dec']
            return ret_dict
        return None


class MPCQuery(object):
    """
    Query the Minor Planet Center for orbital elements of a given object.
    First submit the object's name to the MPC's query-identifier API to get the object's primary designation.
    Next submit the primary designation to the MPC via astroquery to get the object's orbital elements.
    Returns a dictionary of the object's orbital elements.
    """
    def __init__(self, query, scheme):
        self.query = query
        self.keys = [
            'argument_of_perihelion', 'ascending_node', 'eccentricity',
            'inclination', 'mean_anomaly', 'semimajor_axis', 'perihelion_date_jd',
            'epoch_jd', 'perihelion_distance'
        ]
        self.scheme_mapping = {'mpc_minor_planet': 'asteroid', 'mpc_comet': 'comet'}
        self.query_params_mapping = {
            'mpc_minor_planet': ['name', 'designation', 'number'], 'mpc_comet': ['number', 'designation']
        }
        # Object types as described by the MPC: https://www.minorplanetcenter.net/mpcops/documentation/object-types/
        # 50 is for Interstellar Objects
        self.mpc_type_mapping = {'mpc_minor_planet': [0,1,6,20], 'mpc_comet': [6,10,11,20,50]}
        self.scheme = scheme

    def _clean_result(self, result):
        """
        Converts the results from the MPC into a dictionary of floats.
        Extracts the object's name from the query results and adds it to the dictionary.
        """
        cleaned_result = {}
        for key in self.keys:
            try:
                value = float(result[key])
            except (ValueError, TypeError):
                value = None
            cleaned_result[key] = value
        # Build object name from returned Data
        if result.get('number'):
            if result.get('name'):
                # If there is a number and a name, use both with the format "name (number)", otherwise just use number
                cleaned_result['name'] = f"{result['name']} ({result['number']})"
            else:
                cleaned_result['name'] = f"{result['number']}"
                if result.get('object_type'):
                    # Add comet object type if it exists
                    cleaned_result['name'] += result['object_type']
        else:
            cleaned_result['name'] = result.get('designation')
        return cleaned_result

    def get_primary_designation(self):
        """
        Submit the object's name to the MPC's query-identifier API to get the object's preferred primary and
        preliminary designations.
        In the case of multiple possible targets (usually happens for multiple objects with the same name),
        try to disambiguate with the following criteria:
            * Choose the first target with a 'permid' that could be converted into an INT if searching for an asteroid.
            * Return the first target with a 'permid' if searching for a comet.
            * If no 'permid' is found, query the MPC again using the first target with a preliminary designation.
        """
        response = requests.get("https://data.minorplanetcenter.net/api/query-identifier",
                                data=self.query.replace("+", " ").upper())
        identifications = response.json()
        if identifications.get('object_type') and\
                identifications.get('object_type')[1] not in self.mpc_type_mapping[self.scheme]:
            return None, None
        if identifications.get('disambiguation_list'):
            for target in identifications['disambiguation_list']:
                if self.scheme_mapping[self.scheme] == 'asteroid':
                    # If the Target is an asteroid, then the PermID should be an integer
                    try:
                        return int(target['permid']), None
                    except (ValueError, KeyError, TypeError):
                        continue
                elif self.scheme_mapping[self.scheme] == 'comet':
                    # If the Target is a comet, then the PermID should contain a letter (P/C/I)
                    perm_id = target.get('permid')
                    if perm_id:
                        try:
                            # If the PermID is an integer, then it is not a comet, so we keep looking
                            int(target['permid'])
                            continue
                        except (ValueError, KeyError, TypeError):
                            return perm_id, None
                if target.get('unpacked_primary_provisional_designation'):
                    # We need to re-check preliminary designations for multiple targets because these are sometimes
                    # returned by the MPC for disambiguation even though the targets have primary IDs
                    response = requests.get("https://data.minorplanetcenter.net/api/query-identifier",
                                data=target['unpacked_primary_provisional_designation'])
                    identifications = response.json()
                    break
        return identifications['permid'], identifications['unpacked_primary_provisional_designation']

    def get_result(self):
        from astroquery.mpc import MPC
        schemes = []
        if self.scheme in self.scheme_mapping:
            schemes.append(self.scheme)
        else:
            schemes = [*self.scheme_mapping]
        # Get the primary designation of the object and preferred provisional designation if available
        primary_designation, primary_provisional_designation = self.get_primary_designation()
        for scheme in schemes:
            # Make sure the primary designation can be expressed as an integer for asteroids to keep them from being
            # confused for comets
            if primary_designation:
                if scheme == 'mpc_minor_planet':
                    try:
                        primary_designation = int(primary_designation)
                    except ValueError:
                        return None
                params = {'target_type': self.scheme_mapping[scheme], 'number': primary_designation}
                designation = primary_designation
            elif primary_provisional_designation:
                params = {'target_type': self.scheme_mapping[scheme], 'designation': primary_provisional_designation}
                designation = primary_provisional_designation
            else:
                return None
            result = MPC.query_objects_async(**params).json()
            # There are 2 conditions under which we can get back multiple sets of elements:
            # 1. When the search is for a comet and there are multiple types with the same number (e.g. 1P/1I)
            # 2. When the search has multiple sets of elements with different epochs
            if len(result) > 1:
                # Limit results to those that match the object type
                results_that_match_query_type = [elements for elements in result
                                                 if elements.get('object_type', '').lower() in designation.lower()]
                if results_that_match_query_type:
                    result = results_that_match_query_type
            if len(result) > 1:
                recent = None
                recent_time_diff = None
                now = datetime.now()
                # Select the set of elements that are closest to the current date
                for elements in result:
                    if not recent or not recent_time_diff:
                        recent = elements
                        recent_time_diff = math.fabs(
                            (datetime.strptime(recent['epoch'].rstrip('0').rstrip('.'), '%Y-%m-%d') - now).days
                        )
                    else:
                        elements_time_diff = math.fabs(
                            (datetime.strptime(elements['epoch'].rstrip('0').rstrip('.'), '%Y-%m-%d') - now).days
                        )
                        if elements_time_diff < recent_time_diff:
                            recent = elements
                            recent_time_diff = math.fabs(
                                (datetime.strptime(recent['epoch'].rstrip('0').rstrip('.'), '%Y-%m-%d') - now).days
                            )
                return self._clean_result(recent)
            if result:
                return self._clean_result(result[0])
        return None


class NEDQuery(object):
    def __init__(self, query, scheme):
        self.query = query
        self.scheme = scheme

    def get_result(self):
        from astroquery.ipac.ned import Ned
        ret_dict = {}
        try:
            result_table = Ned.query_object(self.query)
        except RemoteServiceError:
            return None
        if len(result_table) == 0:
            return None
        ret_dict['ra_d'] = result_table['RA'][0]
        ret_dict['dec_d'] = result_table['DEC'][0]
        ret_dict['name'] = result_table['Object Name'][0]
        return ret_dict


SIDEREAL_QUERY_CLASSES = [SimbadQuery, NEDQuery]
NON_SIDEREAL_QUERY_CLASSES = [PlanetQuery, MPCQuery]
QUERY_CLASSES_BY_TARGET_TYPE = {'sidereal': SIDEREAL_QUERY_CLASSES, 'non_sidereal': NON_SIDEREAL_QUERY_CLASSES}


def generate_cache_key(query, scheme, target_type):
    cache_key = hashlib.sha3_256()
    cache_key.update(query.encode())
    cache_key.update(scheme.encode())
    cache_key.update(target_type.encode())
    return cache_key.hexdigest()


@app.route('/<path:query>')
def root(query):
    if query == 'favicon.ico':
        return jsonify({})
    logger.log(msg=f'Received query for target {query}.', level=logging.INFO)
    target_type = request.args.get('target_type', '')
    scheme = request.args.get('scheme', '')
    logger.log(msg=f'Using search parameters scheme={scheme}, target_type={target_type}', level=logging.INFO)
    cache_key = generate_cache_key(query, scheme, target_type)
    result = cache.get(cache_key)

    if not result:
        query_classes = SIDEREAL_QUERY_CLASSES + NON_SIDEREAL_QUERY_CLASSES
        if target_type:
            query_classes = QUERY_CLASSES_BY_TARGET_TYPE[target_type.lower()]
        for query_class in query_classes:
            result = query_class(query, scheme.lower()).get_result()
            if result:
                cache.set(cache_key, result, timeout=60 * 60 * 60)
                logger.log(msg=f'Found target for {query} via {query_class.__name__} with data {result}',
                           level=logging.INFO)
                return jsonify(**result)
        logger.log(msg=f'Unable to find result for name {query}.', level=logging.INFO)
        return jsonify({'error': 'No match found'})
    logger.log(msg=f'Found cached target for {query} with data {result}', level=logging.INFO)
    return jsonify(**result)


@app.route('/')
def index():
    instructions = ('This is simbad2k. To query for a sidereal object, use '
                    '/&lt;object&gt;?target_type=&lt;sidereal or non_sidereal&gt;. '
                    'For non_sidereal targets, you must include scheme, which can be '
                    'either mpc_minor_planet or mpc_comet.'
                    'Ex: <a href="/103P?target_type=non_sidereal&scheme=mpc_comet">'
                    '/103P?target_type=non_sidereal&scheme=mpc_comet</a>')
    return instructions


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
