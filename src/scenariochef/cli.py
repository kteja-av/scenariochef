"""ScenarioChef CLI entry point."""

from scenariochef.cx_orchestrator.runtime import run_pipeline


def main() -> None:
    run_pipeline(trajectory_count=20)


if __name__ == "__main__":
    main()
