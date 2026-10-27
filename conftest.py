"""Make repository modules importable when pytest discovers tests from the root."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
