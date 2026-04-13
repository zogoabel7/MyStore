#!/usr/bin/env python3
import sys
import os
import subprocess

if __name__ == "__main__":
    # Get the parent directory of 'mystore'
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Launch precisely via the package module method without path shadowing issues
    sys.exit(subprocess.call([sys.executable, "-m", "mystore"] + sys.argv[1:], cwd=parent_dir))

