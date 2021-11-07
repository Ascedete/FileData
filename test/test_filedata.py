from ..src import *


TEST_FILE = "./Test/testfile.txt"


def test_creation():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)
        assert nd
