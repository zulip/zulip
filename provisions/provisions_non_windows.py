import sys

try:
    import sh
except ImportError:
    import pbs as sh

def main:
    sh.npm.install(**LOUD)
    return 0

if __name__ == "__main__":
    sys.exit(main())
