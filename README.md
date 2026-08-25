# ScenarioChef

Automated scenario generation for OpenSCENARIO and esmini — a compiler-style pipeline that transforms human intent into validated, executable simulation scenarios.

## Phase 1 scope

- **Input:** Natural language, structured specs, crash narratives, trajectory data, existing `.xosc`/`.xodr`
- **Target simulator:** esmini (CARLA / ScenarioRunner deferred)
- **Language:** Python 3.11+

## Architecture

Eleven capability components (C1–C10) plus a DAG orchestrator (CX). See:

- [`component_inventory.md`](component_inventory.md) — component roles, types, and contracts
- [`component_connection_map.md`](component_connection_map.md) — data flow and dependencies
- [`docs/adr/`](docs/adr/) — Architecture Decision Records

Design decisions are frozen in [`docs/checkpoint.md`](docs/checkpoint.md).

## Project layout

```
src/scenariochef/     Python package (one module per component)
docs/                 Research notes, checkpoint, and architecture docs
docs/adr/             Architecture Decision Records
tests/                Unit and integration tests
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

After cloning, install git hooks so Cursor co-author trailers are stripped from commits:

```bash
sh scripts/install-git-hooks.sh
```

Optional: enable the Cursor shell hook in `.cursor/hooks.json` to block `git commit` commands that include `Co-authored-by: Cursor` (see `scripts/block-cursor-coauthor.sh`).

## License

MIT
