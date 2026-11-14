import multiprocessing
import sys

from veu.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
