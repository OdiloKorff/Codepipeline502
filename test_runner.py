import sys

import pytest

from codepipeline.tracing import tracer


def main():
    with tracer.start_as_current_span("Test Phase"):
        pass
    """
        pass
    Run full test suite, including generated integration tests.
    """
    # Run all tests
    sys.exit(pytest.main())

if __name__ == "__main__":
    main()
