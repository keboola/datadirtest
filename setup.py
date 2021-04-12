from distutils.core import setup
import setuptools

setup(
    name='datadirtest',
    version='1.0.2',
    setup_requires=['setuptools_scm'],
    url='https://bitbucket.org/kds_consulting_team/data-dir-test',
    download_url='https://bitbucket.org/kds_consulting_team/data-dir-test',
    packages=setuptools.find_packages(),
    test_suite='tests',
    license="MIT"
)
