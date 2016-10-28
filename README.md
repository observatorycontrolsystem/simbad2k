Simbad2k
========

Simbad for the year 2000

This is a simple web service that returns catalog information for a variety of objects. It makes use of
[astroquery](https://github.com/astropy/astroquery) as well as some other services.

Currently, supported lookups include:

* Major Planets
* Simbad
* MPC
* NED

To add a new source, just create a new class that implements `get_result()` that returns a dictionary and add
the class to `QUERY_CLASSES`.


Up and Running
--------------

pip install the `requirements.txt` and then `./simbad2k.py`
