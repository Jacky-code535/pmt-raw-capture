"""Compatibility entry point; implementation lives in pmt.capture.sampler."""
import sys
from pmt.capture import sampler as implementation
if __name__ == "__main__":
    raise SystemExit(implementation.main())
sys.modules[__name__] = implementation
