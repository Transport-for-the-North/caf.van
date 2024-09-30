""" 
Contains functions that perform checks and provides high level statistics. 
"""
from __future__ import annotations


from pathlib import Path

import pandas as pd

class MatrixReport:

    def __init__(self, matrix: pd.DataFrame):
        self.describe = matrix_describe(matrix)
        self.row_sum = matrix.sum(axis=0)
        self.column_sum = matrix.sum(axis=1)
        self.matrix_sum = matrix.sum().sum()

        print("sandwich")

    @classmethod
    def from_file(cls, path: Path)->MatrixReport:
        matrix = pd.read_csv(path, index_col = 0)
        return cls(matrix)

def matrix_describe(matrix: pd.DataFrame) -> pd.Series:
    
    return matrix.stack().describe()


