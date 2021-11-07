"""
Module defines Result Sum Type and allows to specify Success and Errors more clearly
"""
from typing import Generic, NamedTuple, TypeVar, Union, overload

# from dataclasses import dataclass
ResT = TypeVar("ResT")
# Currently only strings supported
class Success(Generic[ResT]):
    """Wrap a ResT Type in an Success object to signify successful function return

    Args:
        Generic (ResT): from function actually expected type
    """

    def __init__(self, nval: ResT) -> None:
        self.val: ResT = nval


class Error(NamedTuple):
    """Signify erronous operation of function.
    val -> Error Message to be returned from function
    """

    val: str = ""

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Error):
            return False
        else:
            return o.val == self.val

    @overload
    @classmethod
    def error(cls, msg: None) -> "Error":
        ...

    @overload
    @classmethod
    def error(cls, msg: str) -> "Error":
        ...

    @classmethod
    def error(cls, msg: Union[None, str]) -> "Error":
        if msg is None:
            return Error("")
        else:
            return Error(msg)


Result = Union[Success[ResT], Error]


def unwrap(result: Result[ResT]) -> ResT:
    """In case Success is expected return ResT in Success else raise ValueError"""
    if not isinstance(result, Success):
        raise ValueError
    return result.val
