# Skill: Building .xosc with scenariogeneration 0.16.6

Verified recipe (2026-09-02, scenariogeneration 0.16.6, Python 3.11). All classes import
from `scenariogeneration` (`xosc`/`xodr` submodules). Gotchas discovered by trial:

## Entity registration
- `Entities.add_scenario_object(name, CatalogReference(catalogname, entryname))` — NOT
  `add_object` (doesn't exist), NOT `add_entity_byref` (that takes a string).
- Serializing with `add_entity_byref` produces `TypeError: cannot serialize CatalogReference`
  at `ET.tostring` time.

## Storyboard composition
- `Storyboard(init=Init())` — Init is passed to the StoryBoard constructor. `Scenario` has
  NO `add_init` method.
- Chain: `Event.add_action(name, action)` + `Event.add_trigger(ValueTrigger|EntityTrigger)`;
  `Maneuver.add_event(event)`; `ManeuverGroup.add_actor(entity=...)` + `.add_maneuver(...)`;
  `Act.add_maneuver_group(mg)`; `Storyboard.add_act(act)`.
- Raw `Condition`/`ConditionGroup` exist but the ergonomic path is `ValueTrigger`/
  `EntityTrigger` wrappers (they take the *Condition objects as valuecondition/entitycondition).

## Triggers
- `ValueTrigger(name, delay, conditionedge, valuecondition, triggeringpoint="start")` where
  valuecondition ∈ {SimulationTimeCondition, SpeedCondition, ...}.
- `EntityTrigger(name, delay, conditionedge, entitycondition, triggerentity,
  triggeringrule=TriggeringEntitiesRule.any)`.
- `ConditionEdge.none` for plain threshold semantics.
- Enumeration names: `Rule.greaterOrEqual`, `Priority.parallel`, `DynamicsShapes.step`,
  `DynamicsDimension.time` — all in `scenariogeneration.xosc.enumerations`.

## Positions
- `LanePosition(s, offset, lane_id, road_id)` — lane_id/road_id are STRINGS ("1", "-1").
- `WorldPosition(x, y, z=None, ...)`.
- `TeleportAction(position)` for spawn in Init.

## Scenario assembly
```python
xosc.Scenario(name=..., author=..., parameters=xosc.ParameterDeclarations(),
    entities=entities, storyboard=sb, roadnetwork=xosc.RoadNetwork(roadfile=path),
    catalog=xosc.Catalog())
```
- `RoadNetwork(roadfile=...)` — no path/logic kwargs in 0.16.6.
- Serialize: `ET.indent(sc.get_element()); xml = ET.tostring(sc.get_element(), encoding="unicode")`.
  `get_element()` returns an ElementTree Element, not a string.

## OpenDRIVE (xodr) map generation
- `LaneSection(s=0, centerlane=Lane(a=0))` then `.add_left_lane(Lane(a=1))` /
  `.add_right_lane(Lane(a=-1))` — no leftlane/rightlane constructor kwargs.
- `Road(road_id, planview=PlanView(), lanes=Lanes())`, then
  `road.planview.add_geometry(Line(200))`.
- `OpenDrive(name)`, `.add_road(road)`, `.adjust_roads_and_lanes()`, `.get_element()`.
- Lane ids: +1 = left of center (oncoming in RHT), -1 = right driving lane.

## Validation hooks
- `xmlschema` 4.3.2 is installed — XSD validation available for C6 S1 if an XSD file is
  supplied (esmini ships one; OSC 1.0 XSD can be vendored).
