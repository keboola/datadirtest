# Data Dir Test #

This library enables functional testing for Keboola components and processors by comparing expected and 
real output directories.

[**API Docs**](https://htmlpreview.github.io/?https://bitbucket.org/kds_consulting_team/datadirtest/raw/44e514000f232fb6e1f28c35c0eac9c289476f6c/docs/html/datadirtest/datadirtest.html)

### Introduction ###
By defining a direc

## Quickstart ##

### Installation ###

Add to requirements 
```
https://bitbucket.org/kds_consulting_team/datadirtest/get/VERSION_NUMBER.zip#egg=datadirtest
```

Or install via PIP
```
pip install https://bitbucket.org/kds_consulting_team/datadirtest/get/VERSION_NUMBER.zip#egg=datadirtest
```

### Use of the library ###

In the tests folder create a directory structure mimicking the directory structure in production:

```
/path/to/project/tests
└─functional
    └─test-name
      ├─expected-code
      ├─expected
      │ └─data
      │   └─out
      │     ├─files
      │     └─tables
      ├─source
      │ └─data
      │   └─in
      │     ├─files
      │     └─tables
      └─config.json
```

- `source` - contains data folder that would be on the input of the component
- `expected` - contains data folder that is result of the execution against the `source` folder. 
Include only folder that contain some files, e.g. `expected/files/out/file.json` 

The `DataDirTester` looks for the `component.py` script and executes it against the specified source folders, 
the `component.py` should expect the data folder path in the environment variable `KBC_DATADIR`.

By default it looks for the script at this path:
```
/path/to/project
└─src
    └─component.py
```

Then create file `test_functional.py` in the `/path/to/project/tests` folder and input the following:

```
import unittest

from datadirtest import DataDirTester


class TestComponent(unittest.TestCase):

    def test_functional(self):
        functional_tests = DataDirTester()
        functional_tests.run()


if __name__ == "__main__":
    unittest.main()
```

Then run your tests as usual e.g. via `python -m unittest discover` from the root folder.

### Core structure & functionality ###
