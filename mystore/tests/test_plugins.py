import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystore.lib.plugins import PluginManager


def run():
    pm = PluginManager()
    print('PLUGINS', pm.plugins())


if __name__ == '__main__':
    run()
