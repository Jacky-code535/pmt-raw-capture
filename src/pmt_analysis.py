"""Compatibility entry point; implementation lives in pmt.process.reconstruct."""
import sys
from pmt.process import reconstruct as implementation
if __name__ == "__main__":
    raise SystemExit(implementation.main())
sys.modules[__name__] = implementation
