"""ScenarioChef CLI entry point."""

from scenariochef.cx_orchestrator.runtime import run_pipeline


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
