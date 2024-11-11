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

        self.describe = pd.DataFrame()

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

            self.describe["Original_Matrix"] = matrix_describe(matrix)

            translated_describe_label = "Translated_Matrix"

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
        else:
            translated_describe_label = "Matrix"

        self.matrix = matrix
        self.describe[translated_describe_label] = matrix_describe(matrix)

    def write_to_excel(
        self, writer: pd.ExcelWriter, label: Optional[str] = None, output_matrix: bool = False
    ) -> None:

        if label is not None:
            sheet_prefix: str = f"{label}_"
        else:
            sheet_prefix: str = ""

        if len(sheet_prefix) >= 31:
            raise ValueError(
                "label cannot be over 30 characters as the sheets names will"
                " be truncated and will not be unique"
            )

        self.describe.to_excel(writer, sheet_name=f"{sheet_prefix}Summary")

        self.trip_ends.to_excel(writer, sheet_name=f"{sheet_prefix}Trip_Ends")

        if output_matrix is True:
            self.matrix.to_excel(writer, sheet_name=f"{sheet_prefix}Matrix")

    @property
    def trip_ends(self) -> pd.DataFrame:
        return pd.DataFrame({"row_sums": self.row_sum, "col_sums": self.column_sum})

    @property
    def row_sum(self) -> pd.DataFrame:
        return self.matrix.sum(axis=0)

    @property
    def column_sum(self) -> pd.DataFrame:
        return self.matrix.sum(axis=1)

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


def matrix_describe(matrix: pd.DataFrame, almost_zero: Optional[int] = None) -> pd.Series:
    if almost_zero is None:
        almost_zero = 1 / matrix.size
    info = matrix.stack().describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])
    info["sum"] = matrix.sum().sum()
    info["zeros"] = (matrix == 0).sum().sum()
    info["almost_zeros"] = (matrix < almost_zero).sum().sum()
    info["NaNs"] = matrix.isna().sum().sum()
    return info
