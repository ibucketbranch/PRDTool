"""Allow running organizer as a module: python -m organizer."""

import sys

from organizer.cli import main

if __name__ == "__main__":
    sys.exit(main())
