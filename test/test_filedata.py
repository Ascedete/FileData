import pytest


from ..src.filedata import *

TEST_FILE = "./Test/testfile.txt"

data = [("a\nb\nc\n"), ("d\nc\na\n")]


insertion_reference = """// test-case stimulus
`include 'tc.vams'
event SIMULATION_END;

`ifdef CONDITION_MONITOR_ENABLED
    ConditionMonitor simulation_voltage_monitor();
`endif
 
"""
# reading


def test_creation():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)
        assert nd


def test_read():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)
        l = nd.read()
        assert l
        assert l.strip() == "This is a very big file"
        assert nd.read(3).strip() == "--- Marker ---"


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
    assert nd.insert(1, "z")
    assert "".join(nd.text) == "z\n" + data[0]
    assert not nd.insert(0, "evil")


def test_move_cursor():
    nd = FileData(data[0])
    assert nd.move_cursor(FilePosition(3, 1)) is None


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
    assert (l := data.read(res.line))
    assert l.find("event") is not -1
    assert old == data.cursor
    assert seek(data, "event", 5, "Reverse")
