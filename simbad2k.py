#!/usr/bin/env python
from flask import Flask, jsonify
app = Flask(__name__)


class SimbadQuery(object):
    def __init__(self, query):
        from astroquery.simbad import Simbad
        self.simbad = Simbad()
        self.simbad.add_votable_fields('pmra', 'pmdec', 'ra(d)', 'dec(d)')
        self.query = query

    def get_result(self):
        result = self.simbad.query_object(self.query)
        if result:
            ret_dict = {}
            for key in ['RA', 'DEC', 'RA_d', 'DEC_d', 'PMRA', 'PMDEC']:
                if str(result[key][0]) != '--':
                    ret_dict[key.lower()] = result[key][0]
            return ret_dict
        else:
            return None


QUERY_CLASSES = [SimbadQuery]


@app.route('/<query>/')
def root(query):
    for query_class in QUERY_CLASSES:
        result = query_class(query).get_result()
        if result:
            return jsonify(**result)
    return jsonify({'error': 'No match found'})

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
