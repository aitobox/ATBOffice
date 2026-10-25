"""Excel standard error constants and helper utilities."""

from __future__ import annotations

from typing import Any, Final


class ExcelError:
    """Standard Excel formula error type (e.g. #DIV/0!, #VALUE!, #N/A)."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code: str = code

    def __repr__(self) -> str:
        return f"ExcelError('{self.code}')"

    def __str__(self) -> str:
        return self.code

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ExcelError):
            return self.code == other.code
        if isinstance(other, str):
            return self.code == other
        return False

    def __hash__(self) -> int:
        return hash(self.code)


# Singleton error constants
NULL: Final[ExcelError] = ExcelError("#NULL!")
DIV0: Final[ExcelError] = ExcelError("#DIV/0!")
VALUE: Final[ExcelError] = ExcelError("#VALUE!")
REF: Final[ExcelError] = ExcelError("#REF!")
NAME: Final[ExcelError] = ExcelError("#NAME?")
NUM: Final[ExcelError] = ExcelError("#NUM!")
NA: Final[ExcelError] = ExcelError("#N/A")
GETTING_DATA: Final[ExcelError] = ExcelError("#GETTING_DATA")
SPILL: Final[ExcelError] = ExcelError("#SPILL!")
CALC: Final[ExcelError] = ExcelError("#CALC!")

ALL_ERRORS: Final[tuple[ExcelError, ...]] = (
    NULL,
    DIV0,
    VALUE,
    REF,
    NAME,
    NUM,
    NA,
    GETTING_DATA,
    SPILL,
    CALC,
)

ERROR_MAP: Final[dict[str, ExcelError]] = {err.code: err for err in ALL_ERRORS}


def is_error(val: Any) -> bool:
    """Check if a value represents an Excel error."""
    return isinstance(val, ExcelError) or (isinstance(val, str) and val in ERROR_MAP)


def to_error(val: Any) -> ExcelError | None:
    """Convert an error string or ExcelError to its canonical ExcelError instance."""
    if isinstance(val, ExcelError):
        return val
    if isinstance(val, str):
        return ERROR_MAP.get(val.upper())
    return None
