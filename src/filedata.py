from __future__ import annotations
from typing import Generator, List, Literal, Optional, TextIO, Union, overload
from .result import Result, Success, Error

import re

from enum import Enum, auto


class IterationStrategy(Enum):
    """Supported Strategies to traverse filedata object"""

    Reversed = auto()
    Forward = auto()


class FileData:
    """Store and manage File contents with multiple helpers"""

    def __init__(self, text: str) -> None:
        self.text = text
        self._index = 0

    @property
    def text(self) -> List[str]:
        """Represents filetext splitted per Line"""
        return self._text

    @text.setter
    def text(self, new: str):
        text = [line + "\n" for line in new.splitlines()]
        self._text = text

    def set(self, index: int, newline: str) -> bool:
        """
        Set text at line index to newline if index is valid
        """
        if self._check_index_inbounds(index):
            self.text[index] = newline + "\n"
            return True
        else:
            return False

    def patch_line(self, new: str, line_nr: int) -> bool:
        """
        Replace line at line_nr with new
        ERRORS: INDEX_ERROR -> line_nr not in self
        """
        if line_nr > 0 and line_nr < self.max_index:
            if self.text[line_nr] == new:
                return True

            self.text[line_nr] = new
            return True
        else:
            return False

    @classmethod
    def patch(
        cls, filepath: str, new: str, position: Union[int, str, List[str]]
    ) -> Result[str]:
        """
        Try to patch file at filepath with new at position
        if new contains newlines, multiple lines will be inserted
        Returns Success Object in case of correct patching
        Error Messages:
        - FileNotFound, TriggerNotFound, PermissionDenied
        """
        try:
            with open(filepath, "r") as fd:
                nd = cls.data(fd)
        except FileNotFoundError:
            return Error("FileNotFound")

        if isinstance(position, str) or isinstance(position, List):
            pos = nd.seek(position)
            if pos is None:
                return Error("TriggerNotFound")
            pos += 1
        else:
            pos = position

        trigger = new.splitlines()[0]
        # if not (trigger := new.splitlines()[0]):
        #     return Error("TriggerNotFound")

        if nd.seek(trigger, pos):
            # Potentially dangerous assumption...
            return Success("PatchAlreadyDone")

        if isinstance(res := nd.insert(pos, new), Error):
            return res
        try:
            nd.dump(filepath)
            return Success("")
        except PermissionError:
            return Error("PermissionDenied")

    @property
    def max_index(self):
        return len(self.text)

    @overload
    def dump(self, file: TextIO):
        """Dump self to file_io -> make sure to have write permissions"""

    @overload
    def dump(self, file: str):
        """Dump self to file at given str. Write permissions necessary"""

    def dump(self, file: Union[str, TextIO]):
        if isinstance(file, str):
            with open(file, "w", encoding="utf-8") as fd:
                fd.writelines(self.text)
        else:
            file.writelines(self.text)
        return

    def seek(
        self,
        token: Union[str, List[str]],
        offset: int = 0,
        match_case: bool = False,
        strategy: Literal["Reverse", "Forward"] = "Forward",
    ):
        """
        Returns 0-based index if line is found in instance
        If location in filedata is known, offset can speed up search
        Else None
        """
        tmp = self._index
        self._index = offset if strategy == "Forward" else self.max_index - offset
        found = None

        progress = self.newline if strategy == "Forward" else self.previous

        # Configurations
        case_sensitivity = re.IGNORECASE if not match_case else 0

        # ******************
        # *  Single Token  *
        # ******************
        if isinstance(token, str):
            search_pattern = re.compile(
                f".*{re.escape(token)}.*",
                case_sensitivity,
            )
            while l := progress():
                if search_pattern.search(l):
                    found = self._index
                    break
                else:
                    continue

        # **********************
        # *  Multiline tokens  *
        # **********************
        else:
            search_patterns = [
                re.compile(
                    f".*{re.escape(_subtoken)}.*",
                    case_sensitivity,
                )
                for _subtoken in token
            ]
            while l := progress():
                if search_patterns[0].search(l):
                    for pattern in search_patterns[1:]:
                        l = progress()
                        if not l:
                            return
                        if not pattern.search(l):
                            return
                    found = self._index
                    break

        # **********************************
        # *  Restore previous line number  *
        # **********************************
        self._index = tmp
        return found

    @property
    def line_number(self):
        """Equals the currently processed line number"""
        return self._index + 1

    def _check_index_inbounds(self, index: int) -> bool:
        return index > -1 and index < self.max_index

    def readline(self, index: int = -1) -> Optional[str]:
        """
        Read the line at 0 based line number
        If index -1, return currently selected line
        """
        if index == -1:
            index = self._index
        if self._check_index_inbounds(index):
            return self.text[index]
        else:
            return None

    def next(self, direction: Literal["Forward", "Reverse"] = "Forward"):
        """Skip current line in accordance to direction

        Args:
            direction ("Forward"|"Reverse"): Goto next or previous line
        """
        self._index += 1 if direction == "Forward" else -1

    def __iter__(self):
        """Yields a forward incrementing iterator

        Yields:
            Generator over lines in file
        """
        while not (self.max_index) == self._index:
            yield self.text[self._index]
            self.next()

    def newline(self) -> Optional[str]:
        """yields new line if not EOF, else returns nothing
        Progresses line_number of FileData instance!
        """
        self.next()
        return self.readline()

    def previous(self) -> Optional[str]:
        """Yields the previous line if linenumber inbounds
        !!! Decrements index!

        Returns:
            Optional[str]: previous line
        """
        if self.isStart():
            return
        self.next("Reverse")
        return self.readline()

    def isEOF(self):
        return self.max_index < self._index

    def isStart(self):
        return self._index == 0

    def insert(self, line_nr: int, new: str) -> Result[str]:
        """
        Insert new at line_nr to self. line_nr is 0 based
        If position is outside of bounds, returns Error("NOT_INBOUNDS")
        On Success -> Success Object
        If new contains \n -> adds multiple line to self from line_nr

        """
        if self._check_index_inbounds(line_nr):
            splitted = new.splitlines()
            for (i, line) in enumerate(splitted):
                self.text.insert(line_nr + i, line + "\n")
            return Success("")
        return Error("NOT_INBOUNDS")

    @classmethod
    def data(cls, fd: TextIO) -> "FileData":
        return cls(fd.read())
