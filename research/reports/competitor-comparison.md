# Competitor / ecosystem comparison — ScenarioChef

Researched 2026-09-03 via direct web verification (repo titles/licenses fetched live).
Supersedes the blocked sub-agent research plan; sources verified, not guessed.

## Verified ecosystem repos

| Repo | License | Role vs ScenarioChef |
| --- | --- | --- |
| [esmini/esmini](https://github.com/esmini/esmini) | MPL-2.0 | The target simulator. v3.7.2 ships 69 demo .xosc + 20 .xodr (now mirrored in `assets/scenario_db/`). Note: pyoscx license is also MPL-2.0 (docs pages say MIT for examples only). |
| [pyoscx/scenariogeneration](https://github.com/pyoscx/scenariogeneration) | MPL-2.0 (examples MIT) | C5's underlying compiler. 21 xosc + 31 xodr example generator scripts mirrored. Ships an `esmini` runner helper module. |
| [javyduck/ChatScene](https://github.com/javyduck/ChatScene) | MIT | CVPR 2024, arXiv:2405.14062. LLM + knowledge retrieval → safety-critical scenarios in CARLA. Closest LLM-based analog to ScenarioChef's C2/C3 design. |
| [BerkeleyLearnVerify/Scenic](https://github.com/BerkeleyLearnVerify/Scenic) | custom (BSD-family, NOASSERTION on GitHub) | The probabilistic scenario language C4's IR is modeled on (C4-Q1). Full Scenic sampling was deliberately excluded (C4-Q4). |
| [carla-simulator/scenario_runner](https://github.com/carla-simulator/scenario_runner) | MIT | CARLA scenario engine incl. an OpenSCENARIO subsystem; scenario families (FollowLeadingVehicle, ObjectCrossing) are good semantic references. |
| [asam-ev/ASAM-OpenX-Examples](https://github.com/asam-ev/ASAM-OpenX-Examples) | undeclared | Official ASAM samples (signalized T-intersection .xosc OSC 1.4 + .xodr) mirrored reference-only. |

Named systems from the research literature that had **no public code verified** as of
2026-09-03: HASCO (JHU; arXiv describes RAG-over-XSD/esmini-docs + OpenSCENARIO
generation), Txt2Sce (Tsinghua), Chat2Scenario, SERA, ScenarioGPT/LLMScenario. Papers
exist; code either not released or not findable — treat their *ideas* (below) as
adoptable, not their implementations.

## What peers have that ScenarioChef lacks (gap analysis)

1. **Scenario library as regression corpus** (esmini ships 69 runnable demos). *Status:
   CLOSED — mirrored into `assets/scenario_db/esmini-demos/` this session.*
2. **Map variety** (esmini's 20 environments vs our single straight road). *Status:
   CLOSED for acquisition — `assets/scenario_db/esmini-maps/`; wiring multi-map
   selection into C3/C5/C6 is open.*
3. **RAG over scenario corpus for C2/C3** (ChatScene/HASCO pattern): retrieve similar
   scenarios + feature docs before slot-filling. *Open — our scenario DB is the corpus;
   C3's static YAML can gain a retrieval lane.*
4. **Simulator-feedback repair loop** (SERA/HASCO closed loop: run → parse errors →
   regenerate). *Partially open — C9 exists but today only acts on C6 validation
   failures and C8 metrics, not on esmini's own load/runtime errors; C7's RunRecord
   now carries the stdout/stderr needed to feed esmini errors into C9.*
5. **Parameter sweeps / scenario permutations** (esmini `--param_dist` +
   `--param_permutation`; pyoscx ParameterValueDistribution). *Open — maps directly
   onto C9 explore (C9-Q2 search on IR ranges); currently we expand ranges compile-time
   only (C5-Q2) and run each instance separately.*
6. **Video/screenshot rendering of runs** (esmini `--capture_screen`, `--record`).
   *Open — one-flag addition to C7 for visual artifacts persisted via C10.*
7. **HTML report / web viewer of runs** (common in peer tools). *Open.*
8. **Coverage metrics** (which OSC features / scenario categories are covered).
   *Open — esmini's `osc_coverage.txt` (mirrored in esmini-ecosystem/) is the seed.*
9. **Reusable catalogs beyond vehicles** (controller/pedestrian/misc catalogs in
   esmini resources). *Partially closed (vehicles+pedestrians bundled); controllers and
   misc objects open.*
10. **OSC 1.x → 1.4/2.0 awareness** (ASAM sample uses 1.4 with parameter constraints).
    *Deliberately out of Phase-1 scope (OSC 1.1 pin) but the XSD location is documented
    for later.*

## Adopted this session (from the comparison work)

- esmini catalogs as on-disk assets with proper `<CatalogLocations>` (the esmini demos'
  own idiom — this is what made generated scenarios actually run).
- Explicit stop triggers everywhere (all 69 esmini demos declare real StopTriggers; the
  empty-StopTrigger behavior was confirmed fatal).
- `--csv_logger` + `--collision` for C8 (esmini-native data path instead of a synthetic
  CSV schema).
- Scenario/map corpus acquisition (the esmini demo set doubles as knowledge base and
  future regression corpus).

## Recommended next moves (priority order)

1. Wire `--param_dist`/permutation support into C7+C9 → real exploration loop.
2. Feed C7 stderr into C9 repair triggers (simulator-feedback loop, SERA pattern).
3. Multi-map selection: teach C3 to pick a map from the IR description (intersection →
   crossing maps, highway → motorway maps) using the mirrored esmini-maps set.
4. LLM behind the C2 schema gate (C2-Q1 is decided; ChatScene-style retrieval from
   `assets/scenario_db/esmini-demos/` as few-shot context).
5. `--capture_screen` / `--record` artifact capture + minimal HTML run report.
