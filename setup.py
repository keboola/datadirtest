from distutils.core import setup
import setuptools

setup(
    name='datadirtest',
    version='1.5.0',
    setup_requires=['setuptools_scm'],
    url='https://bitbucket.org/kds_consulting_team/datadirtest',
    download_url='https://bitbucket.org/kds_consulting_team/datadirtest',
    packages=setuptools.find_packages(),
    test_suite='tests',
    license="MIT"
)
