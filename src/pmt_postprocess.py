"""Compatibility entry point; implementation lives in pmt.pipeline."""
import sys
from pmt import pipeline as implementation
if __name__ == "__main__":
    raise SystemExit(implementation.main())
sys.modules[__name__] = implementation
