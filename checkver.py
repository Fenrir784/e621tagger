from __future__ import print_function
import sys

if not (
    sys.version_info[0] == 3
    and sys.version_info[1] >= 11
):
    print("Python 3.11 or later is required. The installed version is " + sys.version.split()[0] + ".")
    sys.exit(1)
