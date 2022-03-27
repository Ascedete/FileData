from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing import List, Literal, Optional, TextIO, overload

from .result import Success, Error, IOResult

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

    def __repr__(self):
        msg = f"Line: {self.line} Column: {self.column}"
        return msg


class FileData:
    """Store and manage File contents with multiple helpers"""

    @overload
    def __init__(self, text: str) -> None:
        ...

    @overload
    def __init__(self, text: list[str]) -> None:
        ...

    @overload
    def __init__(self, text: TextIO) -> None:
        ...

    def __init__(self, text: str | list[str] | TextIO) -> None:
        if isinstance(text, str):
            self._text = self._set_text(text)
        elif isinstance(text, list):
            self._text = text
        else:
            self._text = text.readlines()

        self.cursor: FilePosition = FilePosition(1, 1)

    def copy(self):
        """Create a shallow copy of FileData"""
        nd = FileData(self._text)
        nd.cursor = self.cursor
        return nd

    # Basic File Information

    def _line_index(self):
        """
        Index to line in text
        """
        return self.cursor.line - 1

    def _line_end(self):
        return len(self.text[self._line_index()])

    def isEOL(self):
        return (self._line_end()) < self.cursor.column

    def _max_index(self):
        return len(self.text) - 1

    def _isIndexInbounds(self, index: int) -> bool:
        """Will check if index is in range of currently saved text"""
        return index > -1 and index <= self._max_index()

    def isEOF(self):
        """Is cursor still pointing to correct file content or overbounds"""
        if self._line_index() > self._max_index():
            return True

        return self.isEOL()

    def next(self, direction: IterationStrategy = "Forward"):
        if direction == "Forward":
            if self._isIndexInbounds(self._line_index() + 1):
                self.cursor = FilePosition(self.cursor.line + 1, 1)
            else:
                return Error("Cannot move to next line -> EOF")
        elif direction == "Reverse":
            if self._isIndexInbounds(self._line_index() - 1):
                self.cursor = FilePosition(self.cursor.line - 1, 1)
            else:
                return Error("Cannot move to next line -> EOF")

    # Reading file
    @property
    def text(self) -> List[str]:
        """Represents filetext splitted per Line"""
        return self._text

    def _set_text(self, new: str):
        return [line + "\n" for line in new.splitlines()]

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
            return self.text[self._line_index()][self.cursor.column - 1 : -1]

        if linenr > len(self.text):
            return
        else:
            return self.text[linenr - 1]

    def _current_character(self):
        return self.text[self.cursor.line - 1][self.cursor.column - 1]

    def read(self) -> Optional[str]:
        if self.isEOF():
            return
        if not self.isEOL():
            return self._current_character()
        else:
            return self.text[self.cursor.line][0]

    def _next_character_cursor(self):
        if self.cursor.column == self._line_end():
            self.cursor = FilePosition(self.cursor.line + 1, 1)
        else:
            self.cursor = FilePosition(self.cursor.line, self.cursor.column + 1)

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
        if (l := self.readline(new_position.line)) and new_position.column <= len(l):
            self.cursor = new_position
            return
        else:
            return Error(f"Cannot move file cursor to position {new_position}")

    def __iter__(self):
        """Yields a forward incrementing iterator

        Yields:
            Generator over *lines* in file
        """
        while True:
            yield self.text[self._line_index()]
            if isinstance(self.next(), Error):
                break
            else:
                continue

    # Write file content
    def overwrite_line(self, line_nr: int, newline: str) -> IOResult:
        """
        Set text at line index to newline if index is valid
        """
        index = line_nr - 1
        cleaned = newline.rstrip("\n")
        if self._isIndexInbounds(index):
            self.text[index] = cleaned + "\n"
            return
        else:
            return Error(f"given Index {index} not inbounds")

    def insert(self, line_nr: int, new: str):
        """
        Insert new at line_nr to self. line_nr is 1 based
        If position is outside of bounds, returns Error("NOT_INBOUNDS")
        On Success -> Success Object
        If new contains \n -> adds multiple line to self from line_nr
        """
        start_index = line_nr - 1
        if self._isIndexInbounds(start_index):
            splitted = new.splitlines()
            for (i, line) in enumerate(splitted):
                self.text.insert(start_index + i, line + "\n")
            return Success("")
        else:
            return Error(
                f"given line_nr: {line_nr} not inbounds of filedata with length: {len(self.text)}"
            )

    @classmethod
    def data(cls, fd: TextIO) -> "FileData":
        return cls(fd.read())


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
                fd.writelines(data.text)
        except FileNotFoundError:
            return Error(f"Dumping failed -> not enough permission for {file}!")

    else:
        file.writelines(data.text)
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
