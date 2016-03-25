import sys

try:
    import sh
except ImportError:
    import pbs as sh

NO_SYM_LINK = "--no-bin-links"

def main:
    sh.npm.install(NO_SYM_LINK, **LOUD)
    return 0

if __name__ == "__main__":
    sys.exit(main())
