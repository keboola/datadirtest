from .datadirtest import DataDirTester, TestDataDir

# VCR support is optional - only import if dependencies are available
try:
    from .vcr import VCRDataDirTester, VCRTestDataDir

    __all__ = [
        "DataDirTester",
        "TestDataDir",
        "VCRDataDirTester",
        "VCRTestDataDir",
    ]
except ImportError:
    __all__ = [
        "DataDirTester",
        "TestDataDir",
    ]
