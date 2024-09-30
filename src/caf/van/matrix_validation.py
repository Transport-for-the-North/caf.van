""" 
Contains functions that perform checks and provides high level statistics. 
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path

import pandas as pd
import caf.toolkit as ctk


class MatrixReport:

    def __init__(
        self,
        matrix: pd.DataFrame,
        translation: Optional[pd.DataFrame] = None,
        translation_from_col: Optional[str] = None,
        translation_to_col: Optional[str] = None,
        translation_factors_col: Optional[str] = None,
    ):

        if translation is not None:
            if (
                (translation_factors_col is None)
                or (translation_from_col is None)
                or (translation_to_col is None)
            ):
                raise ValueError(
                    "If translation is provided translation_from_col,"
                    " translation_to_col and translation_factors_col "
                    "must also be given"
                )

            matrix = ctk.translation.pandas_matrix_zone_translation(
                matrix,
                translation,
                translation_from_col,
                translation_to_col,
                translation_factors_col,
            )

        elif (
            (translation_factors_col is not None)
            or (translation_from_col is not None)
            or (translation_to_col is not None)
        ):
            raise ValueError(
                "If translation_from_col,"
                " translation_to_col or translation_factors_col are provided,"
                " translation must also be given"
            )
        
        self.matrix = matrix
        self.describe = matrix_describe(matrix)
        self.describe["sum"] =  matrix.sum().sum()
        self.row_sum = matrix.sum(axis=0)
        self.column_sum = matrix.sum(axis=1)




    def write_to_excel(self, writer: pd.ExcelWriter, label: Optional[str]=None, output_matrix: bool = False)->None:

        if label is not None:
            sheet_prefix:str = f"{label}_"
        else: 
            sheet_prefix:str = ""

        self.describe.to_excel(writer, sheet_name=f"{sheet_prefix}Matrix_Summary")

        self.trip_ends.to_excel(writer, sheet_name=f"{sheet_prefix}Trip_Ends")

        if output_matrix is True:
            self.matrix.to_excel(writer, sheet_name=f"{sheet_prefix}Matrix")

        
    
    @property
    def trip_ends(self)->pd.DataFrame:
        return pd.DataFrame({"row_sums":self.row_sum, "col_sums":self.column_sum})

    @classmethod
    def from_file(
        cls,
        path: Path,
        translation_path: Optional[Path] = None,
        translation_from_col: Optional[str] = None,
        translation_to_col: Optional[str] = None,
        translation_factors_col: Optional[str] = None,
    ) -> MatrixReport:
        matrix = pd.read_csv(path, index_col=0)

        if translation_path is not None:
            translation = pd.read_csv(translation_path)
        else:
            translation = None

        return cls(
            matrix,
            translation,
            translation_from_col,
            translation_to_col,
            translation_factors_col,
        )


def matrix_describe(matrix: pd.DataFrame) -> pd.Series:

    return matrix.stack().describe()
