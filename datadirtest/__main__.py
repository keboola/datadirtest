"""Main entry point"""

import sys

from .datadirtest import DataDirTester

if __name__ == "__main__":
    data_dir_path = sys.argv[1]
    data_dir_tester = DataDirTester(data_dir_path)

    if len(sys.argv) == 3:
        script_path = sys.argv[2]
        data_dir_tester = DataDirTester(data_dir_path, component_script=script_path)

    data_dir_tester.run()
