# Scenario Database — sources and provenance

Curated external scenario/map assets for ScenarioChef. Every subfolder lists its origin
URL and license. Text assets only (.xosc/.xodr/.py); no binaries.

## esmini-demos/ — esmini's official demo scenarios (69 files)

- Origin: https://github.com/esmini/esmini/tree/master/resources/xosc (master, fetched 2026-09-03)
- License: MPL-2.0 (esmini repo) — see https://github.com/esmini/esmini/blob/master/LICENSE
- Contents: cut-in variants, ALKS/R157 regulation tests, ACC, lane change, pedestrian
  crossing, highway merge, trajectory/spline following, traffic lights, sumo coupling,
  controllers, parameter distributions, parking, trailers.
- `scenarios/*.xosc` reference catalogs via `../xosc/Catalogs/...` relative paths and maps
  via `../xodr/<name>.xodr` — esmini resolves these relative to its resources layout.

## esmini-maps/ — esmini's OpenDRIVE environments (20 files)

- Origin: https://github.com/esmini/esmini/tree/master/resources/xodr (master, fetched 2026-09-03)
- License: MPL-2.0 (esmini repo)
- Contents: straight/curve/crest roads, circle, crossings, highway, motorway junctions,
  parking lot, two-plus-one road, tunnel, velodrome, length units variants.

## pyoscx-examples/ — scenariogeneration (pyoscx) example generators (52 files)

- Origin: https://github.com/pyoscx/scenariogeneration/tree/master/examples (master, fetched 2026-09-03)
- License: MIT — see https://github.com/pyoscx/scenariogeneration/blob/master/LICENSE
- Contents: `scripts/*.py` (21) scenario-building idioms (conditions, triggers, catalogs,
  synchronization, trajectories, speed profiles, parameter distributions) and
  `xodr-scripts/*.py` (31) OpenDRIVE road-building idioms. These are executable Python
  references for C4/C5 feature expansion, not .xosc files (the project generates .xosc at
  runtime rather than committing them).

## esmini-ecosystem/ — esmini capability reference (7 files, collected 2026-09-02)

- Origin: https://github.com/esmini/esmini (docs/README/source-derived text, collected by
  a research session)
- License: MPL-2.0 (esmini repo) for derived excerpts
- Contents: OpenSCENARIO/OpenDRIVE coverage matrices (`osc_coverage.txt`,
  `odr_coverage.txt`), CLI reference (`commands.txt`, `osg_options.txt`), OSC extension
  schema notes, release notes head.

## asam-osc/ — ASAM official OpenX examples (2 files)

- Origin: https://github.com/asam-ev/ASAM-OpenX-Examples (main, fetched 2026-09-03)
  - ASAM_OpenSCENARIO_XML/Signalized_T_Intersection.xosc (OSC 1.4 — parameter
    constraints, parameter value distribution syntax reference)
  - ASAM_OpenDRIVE/Signalized_T_Intersection.xodr (signalized T-intersection map)
- License: none declared in the repo (no LICENSE file, `"license": null` via API);
  ASAM examples are published by ASAM e.V. for use with the OpenX standards — treat as
  reference-only until ASAM confirms terms. Not for redistribution.
