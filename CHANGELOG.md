# Changelog

## Unreleased

- Added M1b Astropy TEME-to-ITRS position/velocity conversion with an immutable
  ITRS state and explicit Earth-orientation failure/warning policy.
- Added a scoped, offline Vallado Appendix C comparison. Velocity and two
  position components meet predeclared limits; the first position component
  exceeds its 10 mm limit by 3.17 mm and remains an open discrepancy.
- Diagnosed that Skyfield's single-JD Appendix C path reproduces the printed
  vector, while its split-UT1 path agrees with Astropy; retained the original
  strict expected failure pending verification-requirement review.

## M1a orbit kernel and repository setup

- Established source, test-fixture, documentation, and CI structure.
- Implemented validation of archived TLE lines and explicit WGS72 SGP4
  propagation to a typed TEME state in km and km/s.
- Added a package reference-vector test and explicit propagation-error checks.
- Added engineering status and evidence records without claiming frame or
  access functionality.
