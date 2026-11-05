"""requirements-runtime.txt (what ships in the Runtime zip) must be a subset of
requirements.txt (what developers install), with identical pins, so the code
you test is the code you deploy."""

from pathlib import Path

ROOT = Path(__file__).parent.parent


def _pins(path: Path) -> set:
    pins = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pins.add(line.lower())
    return pins


def test_runtime_pins_all_appear_in_dev_requirements():
    runtime = _pins(ROOT / "requirements-runtime.txt")
    dev = _pins(ROOT / "requirements.txt")
    assert runtime, "requirements-runtime.txt has no pins"
    assert runtime <= dev, f"pins only in requirements-runtime.txt: {sorted(runtime - dev)}"


def test_runtime_requirements_exclude_test_tooling():
    assert not any(p.startswith("pytest") for p in _pins(ROOT / "requirements-runtime.txt"))
