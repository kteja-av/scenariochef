# Scenario / map database index

`assets/scenario_db/` holds curated external scenario assets and references, assembled
2026-09-03 by direct scraping (sub-agent waves were blocked by API credit limits; see
`.harness/trajectories/LOOP-2026-09-03.jsonl`).

| Folder | Kind | Files | License | Purpose |
| --- | --- | --- | --- | --- |
| `esmini-demos/scenarios/` | .xosc | 69 | MPL-2.0 | Golden scenario corpus proven to run in esmini; knowledge base for C3 and regression corpus |
| `esmini-maps/` | .xodr | 20 | MPL-2.0 | Diverse OpenDRIVE environments for C4/C5 map selection beyond straight_2lane |
| `pyoscx-examples/scripts/` | .py | 21 | MIT | Executable generation idioms for C5 feature expansion |
| `pyoscx-examples/xodr-scripts/` | .py | 31 | MIT | OpenDRIVE construction idioms (future C5 road synthesis) |
| `esmini-ecosystem/` | .txt/.md/.xml | 7 | MPL-2.0 (excerpts) | esmini capability matrices + CLI reference feeding C3 K3 edges |
| `asam-osc/` | .xosc/.xodr | 2 | undeclared (reference-only) | ASAM official OpenX sample: signalized T-intersection (OSC 1.4 syntax + signalized map) |

All 91 .xosc/.xodr files validated as well-formed XML at assembly time.

## Notable demo scenarios by category

- **Cut-in / lane change**: cut-in.xosc, cut-in_simple, cut-in_parameter_set, alks_cut-in, alks_r157_cut_in_quick_brake, lane_change*.xosc, ltap-od*.xosc
- **Following / ACC**: acc-test.xosc, acc-toggle.xosc, slow-lead-vehicle.xosc, follow_ghost.xosc, follow_reference*.xosc, synchronize.xosc, synch_with_steady_state.xosc
- **Pedestrian / VRU**: pedestrian.xosc, pedestrian_collision.xosc, pedestrian_traj_synch.xosc, alks_pedestrian.xosc, car_walk.xosc, straight_500m_pedestrian.xosc
- **Highway**: highway_driver.xosc, highway_merge.xosc, highway_merge_advanced.xosc, two_plus_one_road.xosc
- **Trajectories**: lane-change_clothoid*.xosc, trajectory-test.xosc, follow_trajectory_by_front_axle.xosc
- **Intersections / signals**: traffic_lights.xosc, routing-test.xosc, ltap-od.xosc (LTAP-OD = left turn across path, opposite direction)

## esmini map inventory (assets/scenario_db/esmini-maps/)

circle_300m, crest-curve, curve_r100, curves, curves_elevation, crossing_8,
crossing_complex, motorway junction/entry variants, parking_lot, parallel_road_lanes,
straight_500m, sig_constraint variants, summit, two_plus_one_road, tunnel, velodrome.
