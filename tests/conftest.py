"""Lets the tests import the Home Assistant-free modules (parse, api) without Home Assistant installed."""

import importlib.util
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "cellar_circle"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"cc_{name}", PKG / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
