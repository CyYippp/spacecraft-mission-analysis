# Validation status

There is **no end-to-end mission-analysis validation** yet. M1b verifies the
selected Astropy TEME-to-ITRS frame transform against independent Vallado
equations at matched split UT1. The direct comparison with the printed
Appendix C x position retains a documented 3.17 mm limit overrun caused by
the numerical time-path difference. Fixed-station ITRS position and ENU
geometry are numerically verified with independent WGS84 equations and
synthetic vectors. Azimuth/elevation/range, access windows, and temporal
coverage are unimplemented; satellite access and pass boundaries remain
unvalidated. There has been no independent Skyfield access comparison and no
GMAT comparison.

The M1a Vanguard 1 check reproduces a reference vector distributed with
the SGP4 implementation. It verifies the software's integration with the
same/reference SGP4 model family. It does **not** establish physical orbit
truth, quantify prediction error, or validate a pass boundary.

Before any future access claim, agree on the frame/time/Earth-orientation
conventions, reference inputs, comparison method, and acceptance thresholds.
Record discrepancies and modelling differences rather than treating an
unmatched external result as an automatic pass or failure.
