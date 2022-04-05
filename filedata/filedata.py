from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing import Literal, Optional, TextIO, overload

from result.result import Success, Error, IOResult

# FileDataResult = Result[str]
IterationStrategy = Literal["Forward", "Reverse"]


@dataclass(init=False, eq=True, unsafe_hash=True, repr=True)
class FilePosition:
    """
    Current position of Cursor in File
    """

    def __init__(self, line: int, column: int) -> None:
        if line > 0 and column > 0:
            self.line = line
            self.column = column
        else:
            raise Exception(
                f"Cannot initialize FilePosition with line: {line}, column: {column} -> arguments need to be >= 1"
            )

    def __add__(self, o: "tuple[int, int]"):
        (l, c) = o
        new_l = self.line + l
        new_c = self.column + c
        if not (new_l and new_c):
            raise ValueError(f"Cannot move Cursor to line: {new_l} column: {new_c}")
        else:
            self.line = new_l
            self.column = new_c
        return self

    def __repr__(self):
        msg = f"Line: {self.line} Column: {self.column}"
        return msg


class FileData:
    """Store and manage File contents with multiple helpers"""

    @overload
    def __init__(self, text: str, remove_whitespace: bool = False) -> None:
        ...

    @overload
    def __init__(self, text: list[str], remove_whitespace: bool = False) -> None:
        ...

    @overload
    def __init__(self, text: TextIO, remove_whitespace: bool = False) -> None:
        ...

    @overload
    def __init__(self, text: dict[int, str], remove_whitespace: bool = False) -> None:
        ...

    def __init__(
        self,
        text: "str | list[str] | TextIO | dict[int, str]",
        remove_whitespace: bool = False,
    ) -> None:
        if isinstance(text, dict):
            self._text = text

        elif isinstance(text, str):
            if remove_whitespace:
                txt = text.replace(" ", "")
                self._text = self._set_text(txt)
            else:
                self._text = self._set_text(text)

        elif isinstance(text, list):
            if remove_whitespace:
                txt = [l.replace(" ", "") for l in text]
            else:
                txt = text
            self._text = self._set_text("".join([l + "\n" for l in txt]))
        else:
            if remove_whitespace:
                txt = text.read().replace(" ", "")

            else:
                txt = text.read()

            self._text = self._set_text(txt)

        self.cursor: FilePosition = FilePosition(1, 1)

    def copy(self):
        """Create a shallow copy of FileData"""
        nd = FileData(self._text)
        nd.cursor = FilePosition(self.cursor.line, self.cursor.column)
        return nd

    # Basic File Information

    def _line_index(self):
        """
        Index to line in text
        """
        return self.cursor.line - 1

    def _line_end(self):
        return len(self.text[self.cursor.line])

    def isEOL(self):
        return self.cursor.column >= self._line_end()

    def _is_line_inbounds(self, line_nr: int):
        try:
            self.text[line_nr]
            return True
        except KeyError:
            return False

    def isEOF(self):
        """Is cursor still pointing to correct file content or overbounds"""
        return not self._is_line_inbounds(self.cursor.line)

    def next(self, direction: IterationStrategy = "Forward"):
        if direction == "Forward":
            if self._is_line_inbounds(self.cursor.line + 1):
                self.cursor = FilePosition(self.cursor.line + 1, 1)
            else:
                return Error("Cannot move to next line -> EOF")
        elif direction == "Reverse":
            if self._is_line_inbounds(self.cursor.line - 1):
                self.cursor = FilePosition(self.cursor.line - 1, 1)
            else:
                return Error("Cannot move to next line -> EOF")

    # Reading file
    @property
    def text(self):
        """Represents filetext splitted per Line"""
        return self._text

    def _set_text(self, new: str):
        input = new.splitlines(keepends=True)
        content = dict([(i, input[i - 1]) for i in range(1, len(input) + 1)])
        return content

    # @text.setter
    # def text(self, new: str):
    #     text = [line + "\n" for line in new.splitlines()]
    #     self._text = text
    #     self.cursor = FilePosition(1, 1)

    def readline(self, linenr: int = -1) -> Optional[str]:
        """
        Read the whole line at line number
        Default or linenr = -1 -> current line
        """
        if linenr == -1:
            return self.text[self.cursor.line][self.cursor.column - 1 : -1]

        if self._is_line_inbounds(linenr):
            return self.text[linenr]
        else:
            return

    def _current_character(self):
        return self.text[self.cursor.line][self.cursor.column - 1]

    def read(self) -> Optional[str]:
        if self.isEOF():
            return
        return self._current_character()

    def _next_character_cursor(self):
        if self.cursor.column == self._line_end():
            self.cursor = FilePosition(self.cursor.line + 1, 1)
        else:
            self.cursor += (0, 1)

    def consume(self) -> Optional[str]:
        if not (c := self.read()):
            return
        self._next_character_cursor()
        return c

    def consume_line(self):
        content = self.readline()
        self.next()
        return content

    def move_cursor(self, new_position: FilePosition) -> IOResult:
        """Move the currently read fileposition to new_position
        if new_position outside of supported range, will raise IndexError
        """
        try:
            self.text[new_position.line][new_position.column - 1]
            self.cursor = new_position
            return
        except IndexError:
            return Error(f"Cannot move file cursor to position {new_position}")
        except KeyError:
            return Error(f"Cannot move file cursor to position {new_position}")

    def __iter__(self):
        """Yields a forward incrementing iterator

        Yields:
            Generator over *lines* in file
        """
        while True:
            yield self.text[self.cursor.line]
            if isinstance(self.next(), Error):
                break
            else:
                continue

    # Write file content
    def overwrite_line(self, line_nr: int, newline: str) -> IOResult:
        """
        Set text at line index to newline if index is valid
        """
        cleaned = newline.rstrip("\n")
        if self._is_line_inbounds(line_nr):
            self.text[line_nr] = cleaned + "\n"
            return
        else:
            return Error(f"given line {line_nr} not inbounds")

    def insert(self, line_nr: int, new: str):
        """
        Insert new at line_nr to self. line_nr is 1 based
        If position is outside of bounds, returns Error("NOT_INBOUNDS")
        On Success -> Success Object
        If new contains \n -> adds multiple line to self from line_nr
        """
        if self._is_line_inbounds(line_nr):
            splitted = new.splitlines(keepends=True)
            splitted.extend(map(lambda x: x.strip("\n"), self.text.values()))
            self._text = self._set_text("".join([l + "\n" for l in splitted]))

            return Success("")
        else:
            return Error(
                f"given line_nr: {line_nr} not inbounds of filedata with length: {len(self.text)}"
            )

    @classmethod
    def data(cls, fd: TextIO) -> "FileData":
        return cls(fd.read())

    def __hash__(self) -> int:
        """Unsafe Hash under Assumption that only cursor will change, not content!"""
        return hash((id(self.text), repr(self.cursor)))

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, FileData):
            return id(self.text) == id(__o.text) and self.cursor == __o.cursor
        else:
            return False


# -------------------------------------
# Helpers to interact with FileData
# ------------------------------------


def seek(
    data: FileData,
    item: str,
    start: Optional[int] = None,
    strategy: IterationStrategy = "Forward",
):
    """
    Seek a string item in data from start and iterate over it's content using strategy
    Will not modify the data
    """

    old_cursor = data.cursor

    if start:
        if not data.move_cursor(FilePosition(start, 1)) is None:
            return

    res = None
    while data.next(strategy) is None:
        l = data.readline()
        assert (
            l is not None
        )  # can afford assert because next returns error if not inbounds
        if (pos := l.find(item)) != -1:
            res = FilePosition(data.cursor.line, pos + 1)
            break

    data.move_cursor(old_cursor)
    return res


@overload
def save_filedata(data: FileData, file: TextIO) -> IOResult:
    """Dump self to file_io -> make sure to have write permissions"""


@overload
def save_filedata(data: FileData, file: str) -> IOResult:
    """Dump self to file at given str. Write permissions necessary"""


@overload
def save_filedata(data: FileData, file: Path) -> IOResult:
    """Dump self to file at given str. Write permissions necessary"""


def save_filedata(data: FileData, file: str | TextIO | Path):
    if isinstance(file, str) or isinstance(file, Path):
        try:
            with open(file, "w", encoding="utf-8") as fd:
                fd.writelines(data.text.values())
        except FileNotFoundError:
            return Error(f"Dumping failed -> not enough permission for {file}!")

    else:
        file.writelines(data.text.values())
    return


# ------------------
# FileData patching
# ------------------


def _get_trigger_start(nd: FileData, position: int | str):
    """Find position where patching should start
    upon error: TriggerNotFound
    """
    if isinstance(position, str):
        pos = seek(nd, item=position)
        if pos is None:
            return Error("TriggerNotFound")
        else:
            return Success(pos.line)
    else:
        return Success(position)


def _needs_patch(nd: FileData, new: str):
    """
    Checks if file has already patch installed.
    If found, false will be returned
    If patch not installed, true

    REFACTORING -> Get Patch position upon success
    """
    content = new.splitlines()
    if not (start := seek(nd, content[0])):
        return True

    for i in range(1, len(content)):
        l = nd.readline(start.line + i)
        if not l or content[i] not in l:
            return True
        else:
            continue
    return False


def insert_content(nd: FileData, new: str, pos: int, path: Path):
    """dump the patch from pos to path"""
    res = nd.insert(pos, new)
    if not res:
        return res
    else:
        return save_filedata(nd, path)


def patch(path: Path, new: str, position: int | str | list[str]):
    """
    Try to patch file at path with new at position
    if new contains newlines, multiple lines will be inserted
    Returns Success Object in case of correct patching
    Error Messages:
    - FileNotFound, TriggerNotFound, PermissionDenied
    """

    try:
        with open(path, "r") as fd:
            nd = FileData.data(fd)
    except FileNotFoundError:
        return Error("FileNotFound")

    # now proceed with patching core
    if isinstance(position, int) or isinstance(position, str):
        # if isinstance(res := _get_trigger_start(nd, position), Error):
        #     return res
        res = _get_trigger_start(nd, position)
    else:
        res = _get_trigger_start(nd, position[0])
    if isinstance(res, Error):
        return res

    start = res.val
    if not (_needs_patch(nd, new)):
        return

    return insert_content(nd, new, start, path)


# Patch only a single line


def patch_line(nd: FileData, new: str, line_nr: int) -> IOResult:
    """
    Replace line at line_nr with new
    """
    nd.overwrite_line(line_nr, new)
