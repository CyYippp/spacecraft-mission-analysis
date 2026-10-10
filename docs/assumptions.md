# Assumptions and boundaries

- Inputs are **archived TLEs only**. One spacecraft is propagated per analysis;
  the current adapter handles one scalar time per call.
- A TLE contains **SGP4 mean elements**, not generic osculating elements. It
  is propagated by `python-sgp4`, not a two-body Keplerian reconstruction.
- The orbit kernel explicitly uses **WGS72** constants. Its Cartesian output
  is **TEME**, with position in **km** and velocity in **km/s**.
- Computational time is scalar Astropy `Time` on the **UTC** scale. The core
  rejects direct Python datetimes, including naive ones. It passes split
  `jd1`/`jd2` values to SGP4 without hidden unit or frame conversion.
- The archived M1a reference case checks reproduction of a published/package
  SGP4 vector. It is **not** a measurement of physical-orbit truth or TLE
  prediction uncertainty.
- Future access analysis is planned as geometric line of sight to fixed
  ground stations with a minimum elevation threshold. Atmospheric refraction,
  terrain masks, link margin, eclipse, and geographic sensor footprint require
  separate scope and evidence.
- TLE prediction quality can degrade with age. Staleness warnings and a
  supported analysis interval are not implemented in M1a and must be defined
  before downstream analysis is presented as usable.
