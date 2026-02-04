from distutils.core import setup
import setuptools

setup(
    name="datadirtest",
    version="1.9.0",
    setup_requires=["setuptools_scm"],
    install_requires=[
        "pathlib",
    ],
    extras_require={
        "vcr": [
            "vcrpy>=4.0.0",
            "freezegun>=1.0.0",
        ],
        "pytest": [
            "pytest>=7.0.0",
        ],
        "all": [
            "vcrpy>=4.0.0",
            "freezegun>=1.0.0",
            "pytest>=7.0.0",
        ],
    },
    url="https://github.com/keboola/datadirtest",
    download_url="https://github.com/keboola/datadirtest",
    packages=setuptools.find_packages(),
    test_suite="tests",
    license="MIT",
    entry_points={
        "pytest11": [
            "datadirtest_vcr = datadirtest.vcr.pytest_plugin",
        ],
    },
)
