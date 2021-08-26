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
      │   ├─ config.json
      │   ├─ set_up.py
      │   ├─ tear_down.py
      │   └─in
      │     ├─files
      │     ├─tables            
```

- `source` - contains data folder that would be on the input of the component
    - it may contain `set_up.py` and `tear_down.py` scripts that are executed before and after each test respectively.
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



**Alternatively** run as:

```
python -m datadirtest /path/to/project/tests/functional [optionally path/to/project/script.py]
```

### Advanced usage ###

In some cases you want to modify the DataDirTest behaviour for instance to prepare the environment for each test, 
or execute some script prior the actual test run.

To achieve this you may extend the `datadirtest.TestDataDir` class. This class is a Test container for each of the 
test data folders and are being triggered as a part of a test suite via `DataDirTester.run()` method.

The `DataDirTester` class takes two additional arguments that allow to specify both the class extending the `DataDirTester` 
with additional functionality and also a context (parameters) that are passed to each `DataDirTester` class instance.

- `test_data_dir_class: Type[TestDataDir]` - a class with additional functionality to execute datadir tests. E.g. `MyCustomDataTest(TestDataDir)`
- `context_parameters` - a dictionary with arbitrary context parameters that are then available in each `TestDataDir` instance 
via `TestDataDir.context_parameters` 

** Example:**

The below code instantiates a pseudo SqlClient and runs the same sequence of queries before each DataDirtest execution.



```python
import unittest

from datadirtest import DataDirTester, TestDataDir

class CustomDatadirTest(TestDataDir):
    def setUp(self):
        sql_client = self.context_parameters['sql_client']
        sql_client.run_query('DROP TABLE IF EXISTS T;')
        sql_client.run_query('CREATE TABLE T AS SELECT 1 AS COLUMN;')


class TestComponent(unittest.TestCase):

    def test_functional(self):
        sql_client = SqlClient("username", "password", "localhost")
        
        functional_tests = DataDirTester(test_data_dir_class=CustomDatadirTest,
                                         context_parameters={'sql_client': sql_client})
        functional_tests.run()


if __name__ == "__main__":
    unittest.main()
```

#### Using set_up and tear_down scripts

You may specify custom scripts that are executed before or after the test execution. Place them into the `source` folder:

```
      ├─source
      │ └─data
      │   ├─ config.json
      │   ├─ set_up.py
      │   ├─ tear_down.py
      │   └─in
      │     ├─files
      │     ├─tables            
```

**Usage**

Each script (`set_up.py` and `tear_down.py`) **must implement** a `run(context: TestDataDir)` method. The `context` parameter then includes the parent
TestDataDir instance with access to `context_parameters` if needed. Both script files are optional. If file is found but there is no `run()` method defined,
the execution fails.

The `set_up.py` may contain following code:

```python
from datadirtest import TestDataDir


def run(context: TestDataDir):
    # get value from the context parameters injected via DataDirTester constructor
    sql_client = context.context_parameters['sql_client']
    sql_client.run_query('DROP TABLE IF EXISTS T;')
    sql_client.run_query('CREATE TABLE T AS SELECT 1 AS COLUMN;')
    print("Running before script")
```

It will run the above script specific for the current test (folder) before the actual test execution