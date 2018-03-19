#!/usr/bin/env python
from flask import Flask, jsonify, request
from flask_cors import CORS
from astroquery.exceptions import RemoteServiceError
from werkzeug.contrib.cache import SimpleCache, NullCache
cache = SimpleCache()
app = Flask(__name__)
CORS(app)


class PlanetQuery(object):
    def __init__(self, query):
        self.query = query.lower()

    def get_result(self):
        import json
        with open('planets.json', 'r') as planets:
            p_json = json.loads(planets.read())
        return p_json.get(self.query)


class SimbadQuery(object):
    def __init__(self, query):
        from astroquery.simbad import Simbad
        self.simbad = Simbad()
        self.simbad.add_votable_fields('pmra', 'pmdec', 'ra(d)', 'dec(d)')
        self.query = query

    def get_result(self):
        result = self.simbad.query_object(self.query)
        print(result)
        if result:
            ret_dict = {}
            for key in ['RA', 'DEC', 'RA_d', 'DEC_d', 'PMRA', 'PMDEC']:
                if str(result[key][0]) not in ['--', '']:
                    ret_dict[key.lower()] = result[key][0]
            return ret_dict
        return None


class MPCQuery(object):
    def __init__(self, query):
        self.query = query
        self.keys = [
            'argument_of_perihelion', 'ascending_node', 'eccentricity',
            'inclination', 'mean_anomaly', 'semimajor_axis', 'perihelion_date_jd',
            'epoch_jd', 'perihelion_distance'
        ]

    def get_result(self):
        from astroquery.mpc import MPC
        params = {'name': self.query}
        result = MPC.query_object_async(**params).json()
        if result:
            return {k: float(result[0][k]) for k in self.keys}
        return None


class NEDQuery(object):
    def __init__(self, query):
        self.query = query

    def get_result(self):
        from astroquery.ned import Ned
        ret_dict = {}
        try:
            result_table = Ned.query_object(self.query)
        except RemoteServiceError:
            return None
        ret_dict['ra_d'] = result_table['RA(deg)'][0]
        ret_dict['dec_d'] = result_table['DEC(deg)'][0]
        return ret_dict

SIDEREAL_QUERY_CLASSES = [SimbadQuery, NEDQuery]
NON_SIDEREAL_QUERY_CLASSES = [PlanetQuery, MPCQuery]

@app.route('/<query>')
def root(query):
    target_type = request.args.get('target_type', None)
    result = cache.get(query if target_type is None else query + '_' + target_type.lower())
    if not result:
        query_classes = SIDEREAL_QUERY_CLASSES + NON_SIDEREAL_QUERY_CLASSES
        if target_type is not None:
            query_classes = SIDEREAL_QUERY_CLASSES if target_type.lower() == 'sidereal' else NON_SIDEREAL_QUERY_CLASSES
        for query_class in query_classes:
            result = query_class(query).get_result()
            if result:
                cache.set(query, result, timeout=60 * 60 * 60)
                return jsonify(**result)
        return jsonify({'error': 'No match found'})
    return jsonify(**result)


@app.route('/')
def index():
    return 'This is simbad2k. To query for an object, use /&lt;object&gt;/. Ex: <a href="/m51/">/m51/</a>'


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
