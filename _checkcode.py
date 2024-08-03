#! /usr/bin/env python3
from logging import getLogger, basicConfig,  WARNING
import sys
logg = getLogger("CHECK")

from optparse import OptionParser
cmdline = OptionParser("%prog -opts filename...")
cmdline.add_option("-v", "--verbose", action="count", default=0,
                   help="increase logging level")
opt, args = cmdline.parse_args()
basicConfig(level=WARNING - 10 * opt.verbose)

warnings = 0
errors = 0
for filename in args:
    for lineno, line in enumerate(open(filename)):
        if "logg.fatal" in line:
            # I tend to use logg.fatal instead of printf-debugging
            logg.error(" %s:%s found logg.fatal\n\t%s", filename, lineno, line)
            errors += 1
if errors:
    sys.exit(1)
