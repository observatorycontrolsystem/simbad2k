#!/usr/bin/env python
from datetime import datetime
import logging
from logging.config import dictConfig
import math

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
        with open('planets.json', 'r') as planets:
            p_json = json.loads(planets.read())
        return p_json.get(self.query)


class SimbadQuery(object):
    def __init__(self, query, scheme):
        from astroquery.simbad import Simbad
        self.simbad = Simbad
        self.simbad.add_votable_fields('pmra', 'pmdec', 'ra(d)', 'dec(d)', 'plx', 'main_id')
        self.query = query
        self.scheme = scheme

    def get_result(self):
        result = self.simbad.query_object(self.query)
        if result:
            ret_dict = {}
            for key in ['RA', 'DEC', 'RA_d', 'DEC_d', 'PMRA', 'PMDEC', 'PLX_VALUE', 'MAIN_ID']:
                if str(result[key][0]) not in ['--', '']:
                    ret_dict[key.lower()] = result[key][0]
            if ret_dict.get('main_id'):
                ret_dict['name'] = ret_dict['main_id']
                del ret_dict['main_id']
            return ret_dict
        return None


class MPCQuery(object):
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
        self.scheme = scheme

    def _clean_result(self, result):
        cleaned_result = {}
        for key in self.keys:
            try:
                value = float(result[key])
            except (ValueError, TypeError):
                value = None
            cleaned_result[key] = value
        return cleaned_result

    def get_result(self):
        from astroquery.mpc import MPC
        schemes = []
        if self.scheme in self.scheme_mapping:
            schemes.append(self.scheme)
        else:
            schemes = [*self.scheme_mapping]
        for scheme in schemes:
            for query_param in self.query_params_mapping[scheme]:
                params = {'target_type': self.scheme_mapping[scheme], query_param: self.query}
                result = MPC.query_objects_async(**params).json()
                ret_dict = {}
                if len(result) > 1:
                    # Return the set of orbital elements closest to the current date
                    recent = None
                    recent_time_diff = None
                    now = datetime.now()
                    for ephemeris in result:
                        if not recent or not recent_time_diff:
                            recent = ephemeris
                            recent_time_diff = math.fabs(
                                (datetime.strptime(recent['epoch'].rstrip('0').rstrip('.'), '%Y-%m-%d') - now).days
                            )
                        else:
                            ephemeris_time_diff = math.fabs(
                                (datetime.strptime(ephemeris['epoch'].rstrip('0').rstrip('.'), '%Y-%m-%d') - now).days
                            )
                            if ephemeris_time_diff < recent_time_diff:
                                recent = ephemeris
                                recent_time_diff = math.fabs(
                                    (datetime.strptime(recent['epoch'].rstrip('0').rstrip('.'), '%Y-%m-%d') - now).days
                                )
                    ret_dict = self._clean_result(recent)
                elif len(result) == 1:
                    ret_dict = self._clean_result(result[0])

                if ret_dict:
                    ret_dict['name'] = self.query
                    return ret_dict

            return None


class NEDQuery(object):
    def __init__(self, query, scheme):
        self.query = query
        self.scheme = scheme

    def get_result(self):
        from astroquery.ned import Ned
        ret_dict = {}
        try:
            result_table = Ned.query_object(self.query)
        except RemoteServiceError:
            return None
        if len(result_table) == 0:
            return None
        ret_dict['ra_d'] = result_table['RA(deg)'][0]
        ret_dict['dec_d'] = result_table['DEC(deg)'][0]
        ret_dict['name'] = self.query
        return ret_dict


SIDEREAL_QUERY_CLASSES = [SimbadQuery, NEDQuery]
NON_SIDEREAL_QUERY_CLASSES = [PlanetQuery, MPCQuery]
QUERY_CLASSES_BY_TARGET_TYPE = {'sidereal': SIDEREAL_QUERY_CLASSES, 'non_sidereal': NON_SIDEREAL_QUERY_CLASSES}


def generate_cache_key(query, scheme, target_type):
    return f'{query}{scheme}{target_type}'


@app.route('/<path:query>')
def root(query):
    logger.log(msg=f'Received query for target {query}.', level=logging.INFO)
    target_type = request.args.get('target_type', '')
    scheme = request.args.get('scheme', '')
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
                    '/m51?target_type=sidereal&scheme=mpc_comet</a>')
    return instructions


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
