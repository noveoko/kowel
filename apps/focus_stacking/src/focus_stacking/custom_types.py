# src/focus_stacking/custom_types.py
from typing import TypeVar, Union
import tkinter as tk
from pathlib import Path
from typing_extensions import TypeAlias

# Variable types
TkStringVar: TypeAlias = tk.StringVar
TkBoolVar: TypeAlias = tk.BooleanVar
TkIntVar: TypeAlias = tk.IntVar
TkDoubleVar: TypeAlias = tk.DoubleVar

# Union types for variables that can be either Tkinter vars or basic types
VarString: TypeAlias = Union[str, TkStringVar]
VarBool: TypeAlias = Union[bool, TkBoolVar]
VarInt: TypeAlias = Union[int, TkIntVar]
VarFloat: TypeAlias = Union[float, TkDoubleVar]

# Combined variable type for all possible values
VarValue: TypeAlias = Union[str, bool, int, float]
VarAny: TypeAlias = Union[VarString, VarBool, VarInt, VarFloat]

# Command types
CommandList: TypeAlias = list[Union[str, Path]]


class MockTk:
    """Mock Tkinter root for testing"""

    def __init__(self):
        self.calls = []

    def after(self, ms, func=None, *args):
        if func:
            func(*args)

    def update(self):
        pass

    def destroy(self):
        pass

    def quit(self):
        pass
