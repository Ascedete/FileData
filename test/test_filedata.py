import pytest


from ..src import *


TEST_FILE = "./Test/testfile.txt"

data = [("a\nb\nc\n"), ("d\nc\na\n")]


insertion_reference = """// test-case stimulus
`include 'tc.vams'
event SIMULATION_END;

`ifdef CONDITION_MONITOR_ENABLED
    ConditionMonitor simulation_voltage_monitor();
`endif
 
"""


def test_creation():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)
        assert nd


def test_seek_casesensitive():
    input = "lala evil_hint\n better EVIL_hint\n best Evil_Hint"
    nd = FileData(input)
    assert nd.seek("Evil_Hint", match_case=True) == 2


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
    nd.insert(0, "z")
    assert "".join(nd.text) == "z\n" + data[0]


def test_combined():
    tb_stim_snippet = """// test-case stimulus
`include 'tc.vams'
 
"""
    nd = FileData(tb_stim_snippet)
    pos = nd.seek("`include 'tc.vams'")
    assert pos
    nd.insert(
        pos + 1,
        """event SIMULATION_END;

`ifdef CONDITION_MONITOR_ENABLED
    ConditionMonitor simulation_voltage_monitor();
`endif
""",
    )
    joined = "".join(nd.text)
    assert insertion_reference == joined


def test_patch_line():
    nd = FileData(data[0])
    nd.patch_line("PATCH", 1)
    assert nd.text[1] == "PATCH"


def test_previous():
    nd = FileData(data[0])
    l = nd.readline()
    nd.next()
    assert nd.previous() == l


def test_seek_reverse():
    with open(TEST_FILE, "r") as fd:
        nd = FileData.data(fd)

    assert 8 == nd.seek("Far away", strategy="Reverse")
