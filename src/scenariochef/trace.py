"""Shared trace emitter: one formatted line per pipeline step."""


def emit(step, component, direction, token) -> None:
    print(f"[step:{step:02d}] {component:<3} {direction:<3} {token}")
