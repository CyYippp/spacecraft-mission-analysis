# Changelog

## Unreleased

- Added M1b Astropy TEME-to-ITRS position/velocity conversion with an immutable
  ITRS state and explicit Earth-orientation failure/warning policy.
- Added a scoped, offline Vallado Appendix C comparison. The direct
  production-minus-printed x-position residual exceeds the 10 mm limit by
  3.17 mm and remains recorded as a numerical reference discrepancy.
- Diagnosed that Skyfield's single-JD Appendix C path reproduces the printed
  vector, while its split-UT1 path agrees with Astropy.
- Approved a verification-reference change: the printed vector is retained as
  historical reproduction evidence, and an independent matched split-UT1
  calculation is the active production acceptance reference. The original
  10 mm position and 0.1 mm/s velocity limits remain unchanged; no production
  physics or frame code changed.

## M1a orbit kernel and repository setup

- Established source, test-fixture, documentation, and CI structure.
- Implemented validation of archived TLE lines and explicit WGS72 SGP4
  propagation to a typed TEME state in km and km/s.
- Added a package reference-vector test and explicit propagation-error checks.
- Added engineering status and evidence records without claiming frame or
  access functionality.
