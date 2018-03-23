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


Querying
--------

Simbad2k can query for both sidereal and non-sidereal targets, and, from
non-sidereal targets, both comets and asteroids. The `scheme` query parameter
is required for non-sidereal targets and has valid values of `mpc_minor_planet`
and `mpc_comet`. Examples of three queries are as follows:

`/m51?target_type=sidereal`
`/103P?target_type=non_sidereal&scheme=mpc_comet`
`/ceres?target_type=non_sidereal&scheme=mpc_minor_planet`