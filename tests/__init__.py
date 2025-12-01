# file: tests/__init__.py
import pathlib
import sys

# Add src to path so tests can import the package
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
