# Validation status

There is **no end-to-end mission-analysis validation** yet. TEME-to-ITRS,
station geometry, access windows, and temporal coverage are unimplemented.
There has been no independent Skyfield comparison and no GMAT comparison.

The current Vanguard 1 check reproduces a reference vector distributed with
the SGP4 implementation. It verifies the software's integration with the
same/reference SGP4 model family. It does **not** establish physical orbit
truth, quantify prediction error, or validate a pass boundary.

Before any future access claim, agree on the frame/time/Earth-orientation
conventions, reference inputs, comparison method, and acceptance thresholds.
Record discrepancies and modelling differences rather than treating an
unmatched external result as an automatic pass or failure.
