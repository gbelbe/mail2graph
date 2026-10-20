from pathlib import Path

from pytest_bdd import scenarios

scenarios(*sorted(str(p) for p in Path(__file__).parent.glob("*.feature")))
