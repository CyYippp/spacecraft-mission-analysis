# Spacecraft Mission Analysis Tool

**Problem:** Given an archived two-line element set (TLE), fixed ground stations
and a UTC interval, when is a spacecraft geometrically above each station's
elevation mask, and how much of the interval has access through any station?
This Python portfolio demonstrator answers that bounded question for one
spacecraft per run. It produces traceable access windows and temporal coverage
in versioned JSON and CSV. It is intended for reviewing the analysis method,
software engineering and evidence, not for operational pass prediction.

**Start here:** [v0.1.0 release case and decision](docs/release-v0.1.0.md) ·
[verification record](docs/verification.md) ·
[validation record](docs/validation.md) ·
[issues and limitations](docs/issues.md) ·
[engineering decisions](docs/decisions/README.md).

## Method

```text
archived TLE → WGS72 SGP4 / TEME state → Astropy TEME → ITRS (Earth fixed)
             → fixed WGS84 station / local ENU → geometric elevation − mask
             → 5 s discovery grid → sign-change bracket → Brent root refinement
             → per-station access windows → temporal coverage union and gaps
             → versioned JSON / six CSV files
```

The [architecture](docs/architecture.md) explains the interfaces and frame
conventions. The discovery samples find candidate crossings; Brent refinement
locates each bracketed threshold event. Access also records a bounded peak
elevation estimate. The output describes geometric visibility, not link
performance or a schedule.

## Worked result: archived Vanguard 1 case

The committed [input and result](examples/vanguard_run/) use Vanguard 1
(catalogue 00005), 2000-06-27 20:00–20:40 UTC, a 10° mask and two **synthetic**
WGS84 stations at 0°N 0°E and 1°N 1°E. The run detects one window per station;
their overlap forms **one merged interval with 1229.268 s of access, or 51.22%
of the 40-minute analysis interval**. The Greenwich window is
20:11:00.831787810–20:31:30.099808909 UTC. The totals are rounded here; the
timestamp is copied from the saved [run.json](examples/vanguard_run/run.json).
This is an archived calculation, not a measured pass.

The example selects an explicit, hashed **test-only zero Earth-orientation
table** to make this archived case reproducible. It does not represent the
physical Earth orientation at the event date.

## Verification & Validation

- **Reference and component verification:** the SGP4 adapter passes fixed
  Vanguard TEME position/velocity limits against a published `python-sgp4`
  reference vector. Matched split-UT1 frame equations, WGS84 station/ENU
  geometry, analytic elevation crossings and peaks, and hand-calculated
  coverage cases test the calculation stages separately. The direct printed
  Vallado frame vector retains a documented **3.17 mm x-position limit
  overrun**; the [frame decision](docs/decisions/0001-matched-split-ut1-frame-reference.md)
  explains the corrected reference method without relaxing that limit.
- **Skyfield comparison:** a frozen hold-out passed downstream elevation and
  event-timing criteria under matched Earth orientation. Skyfield and this
  tool share `sgp4==2.27`, so this is cross-implementation evidence for the
  downstream calculation, not an independent SGP4 accuracy check.
- **GMAT comparison:** Phase A passed bounded event-location criteria with
  GMAT R2026a using an **imported production trajectory**. Phase B checked
  initial-state transfer and numerical repeatability under **different
  dynamics**; its propagation divergence is a cross-model diagnostic, not a
  same-model pass-time accuracy result. See the [Phase A](validation/gmat/phase_a/README.md)
  and [Phase B](validation/gmat/phase_b/README.md) evidence.
- **Failed gates and correction:** the GMAT STK `Fixed` transfer and first ICRF
  sample gate remain recorded as failed. [Decision 0004](docs/decisions/0004-gmat-stk-position-transfer-gate.md)
  changed the validation method to a predeclared continuous-time position
  gate appropriate to GMAT's documented interpolation; that gate passed before
  Phase A proceeded. The earlier failures were not relabelled as passes.

The [live requirements](docs/requirements.md) give MA-01–MA-08 dispositions;
the [verification](docs/verification.md) and [validation](docs/validation.md)
records give criteria, observed results and independence boundaries.

## Limits

Results are geometric-only: no atmospheric refraction, link budget, eclipse,
sensor footprint or operational scheduling. TLE age and Earth-orientation
inputs affect the result, and physical pass-time uncertainty has not been
quantified. The finite 5 s discovery grid can miss short near-grazing access;
the bounded peak search cannot certify an unseen higher peak between samples.
Independent same-model SGP4 accuracy remains open. This is **not operational,
certified or flight-qualified** software. See the [issue register](docs/issues.md)
for dispositions.

## Reproduce the archived case

Python 3.11 or newer is required. Dependencies and developer tools are pinned
in [pyproject.toml](pyproject.toml). From the repository root, a reviewer can
install and run the canonical archived case:

```text
python -m pip install .
spacecraft-mission-analysis examples/vanguard_run/config.json --output-dir output/vanguard
```

Expected: exit `0`, `SUCCESS`, two station windows, one merged interval,
`output/vanguard/run.json` and six CSV files under `output/vanguard/csv/`.
The command refuses to overwrite existing analysis files; choose a fresh
output directory for a rerun. The [example record](examples/vanguard_run/README.md)
contains exact inputs, saved file hashes and reproduction notes. The
[input](docs/input-schema-v1.md) and [output](docs/run-schema-v1.md) contracts
define schemas and failure behaviour.

The repository is the source of truth for current implementation state:
[requirements](docs/requirements.md), [assumptions](docs/assumptions.md),
[architecture](docs/architecture.md), [verification](docs/verification.md),
[validation](docs/validation.md), [issues](docs/issues.md) and
[decisions](docs/decisions/README.md) trace claims to their evidence.
