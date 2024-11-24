# src/types.py
from typing import TypeVar, Union
import tkinter as tk

TkVar = TypeVar("TkVar", tk.StringVar, tk.BooleanVar, tk.IntVar, tk.DoubleVar)
VarValue = Union[str, bool, int, float]
