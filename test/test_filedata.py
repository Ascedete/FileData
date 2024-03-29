from shutil import copy
import pytest
from os import remove

from pathlib import Path
from filedata.filedata import *


# ********************************************
# *  Provide a way to make temporal changes  *
# ********************************************


@dataclass
class FileTester:
    reference: Path
    persistent: bool = False

    def __post_init__(self):
        self.__temp_file = self.reference.with_name("_tmp")

    def __enter__(self):
        copy(self.reference, self.__temp_file)
        return self.__temp_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.persistent:
            try:
                remove(self.__temp_file)
            except NotImplementedError:
                return


TEST_FILE = Path("./test/testfile.txt")

data = [("a\nb\nc\n"), ("d\nc\na\n")]


insertion_reference = """// test-case stimulus
`include 'tc.vams'
event SIMULATION_END;

`ifdef CONDITION_MONITOR_ENABLED
    ConditionMonitor simulation_voltage_monitor();
`endif
 
"""
# reading


def test_fileposition_representation():
    print(FilePosition(19, 10))


def test_creation():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)
        assert nd


def test_readline():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)
        l = nd.readline()
        assert l
        assert l.strip() == "This is a very big file"
        assert nd.readline(3).strip() == "--- Marker ---"


def test_read():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)

    c = nd.read()
    assert c and c == "T"


def test_consume():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)
        c = nd.read()
        assert c == nd.consume()
        assert c is not nd.read() and nd.read() == "h"

    nd = FileData(data[0])
    assert nd.consume() == "a"
    assert nd.read() == "\n"
    assert nd.consume() == "\n"
    assert nd.read() == "b"


def test_copy():
    d1 = FileData(data[0])
    d1.next()
    d2 = d1.copy()
    assert d2.read() == d1.read() == "b"
    # check correct copying after outer position
    nd = nd = FileData("Alla.\nNext\n")
    nd.move_cursor(FilePosition(2, 5))
    nd.consume()
    d = nd.copy()
    assert d.read() is None


@pytest.mark.parametrize("input", data)
def test_iteration(input: str):
    """Test that correct iteration is possible"""
    nd = FileData(input)
    given = []
    splitted = input.splitlines()
    for (i, c) in enumerate(nd):
        assert c.strip() == splitted[i]
        given.append(c)
    assert len(given) == len(splitted)


def test_insert():
    """Test if insert of new string works correctly"""
    input = data[0]
    nd = FileData(input)
    res = nd.insert(1, "z")
    assert res
    assert "".join(res.val.text.values()) == "z\n" + data[0]
    assert not nd.insert(0, "evil")


def test_move_cursor():
    nd = FileData(data[0])
    assert nd.move_cursor(FilePosition(3, 1))
    c = nd.read()
    assert c and c == "c"
    assert not nd.move_cursor(FilePosition(4, 1))


def test_previous():
    nd = FileData(data[0])
    l = nd.read()
    nd.next()
    nd.next("Reverse")
    assert nd.read() == l
    nd.next()
    assert nd.read() != l


def test_seek():
    data = FileData(insertion_reference)
    old = data.cursor

    assert (res := seek(data, "event"))
    assert (l := data.readline(res.line))
    assert l.find("event") is not -1
    assert old == data.cursor
    assert seek(data, "event", 5, "Reverse")


def test_hashable():
    nd1 = FileData("Hallo")
    nd2 = FileData("Hello")
    dict = {nd1.copy(): "ND1", nd2.copy(): "ND2"}
    assert dict[nd1] == "ND1" and dict[nd2] == "ND2"

    nd1.move_cursor(FilePosition(1, 3))
    with pytest.raises(KeyError):
        dict[nd1]

    nd1.move_cursor(FilePosition(1, 1))
    assert dict[nd1] == "ND1"

    # WILL NOT WORK FOR MUTATED FILECONTENT!
    # nd1.overwrite_line(1, "Evil!")
    # with pytest.raises(KeyError):
    #     dict[nd1]


def test_patch():
    with FileTester(TEST_FILE) as tf:
        assert patch(tf, "Hallo", "--- Marker ---")
        with open(tf, "r") as nd:
            data = FileData(nd)
            assert data.text[4] == "Hallo\n"
            assert len(data.text) == 10

        assert not patch(tf, "Evil", "Notfound")
        assert not patch(Path("Not/found"), "Hallo", 1)
