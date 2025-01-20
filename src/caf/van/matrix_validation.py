""" 
Contains functions that perform checks and provides high level statistics. 
"""

from __future__ import annotations

# Built-Ins
from pathlib import Path
from typing import Optional

# Third Party
import caf.toolkit as ctk
import pandas as pd


class MatrixReport:
    """Produce report of statistics for a given `matrix`.

    Parameters
    ----------
    matrix : pd.DataFrame
        2D matrix with columns and index containing zones.
    translation : pd.DataFrame, optional
        Factors for translating matrix from current zone system
        to a new one for reporting, if not given then the matrix
        zone system remains unchanged.
        If this is given then all column name parameters must
        also be given.
    translation_from_col : str, optional
        Column name in `translation` containing current matrix zones.
    translation_to_col : str, optional
        Column name in `translation` containing output matrix zones.
    translation_factors_col : str, optional
        Column name in `translation` containing translation factors.

    Raises
    ------
    ValueError
        If `translation` is given without the column names, or visa versa.

    See Also
    --------
    matrix_describe: for producing descriptive statistics of a matrix.
    """

    describe: pd.DataFrame
    """Dictionary containing statistics for the matrix. If `translation`
    is enabled this will contain "Original_Matrix" and "Translated_Matrix"
    columns, otherwise it will contain a single column named "Matrix".
    """

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
        """Write matrix report to multiple sheets in an Excel file.

        Writes 2 (or 3) sheets to the file with names "`label`_Summary",
        "`label`_Trip_Ends" and "`label`_Matrix" (if `output_matrix` is True).

        Parameters
        ----------
        writer : pd.ExcelWriter
            Excel file to write reports to.
        label : str, optional
            Prefix for sheet names, will have "_" and the report name appended.
        output_matrix : bool, default False
            If True outputs the matrix to an Excel sheet, False is recommended
            for larger matrices as writing large data to Excel may be slow.
        """
        if label is not None:
            sheet_prefix: str = f"{label}_"
        else:
            sheet_prefix = ""

        if len(sheet_prefix) >= 22:
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
        """Matrix trip ends, with columns "row_sums" and "col_sums"."""
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
        """Produce matrix report by loading matrix from CSV file.

        See Also
        --------
        MatrixReport: for information on expected format of matrix and
            other parameters.
        """
        matrix = pd.read_csv(path, index_col=0)

        if translation_path is not None:
            translation = pd.read_csv(
                translation_path,
                usecols=[translation_from_col, translation_to_col, translation_factors_col],
            )
        else:
            translation = None

        return cls(
            matrix,
            translation,
            translation_from_col,
            translation_to_col,
            translation_factors_col,
        )


def matrix_describe(matrix: pd.DataFrame, almost_zero: Optional[float] = None) -> pd.Series:
    """Provide descriptive statistics of `matrix`.

    Parameters
    ----------
    matrix : pd.DataFrame
        2D matrix of values with zones as the columns and index.
    almost_zero : float, optional
        Any values less than this are counted as almost zero in the output.
        If not given it is calculated at `1 / matrix.size`.

    Returns
    -------
    pd.Series
        Matrix statistics containing: percentiles (5%, 25%, 50%, 75% and 95%),
        mean, std, min, max, sum (total), zeros (count), almost zeros (count)
        and NaNs (count).
    """
    if almost_zero is None:
        almost_zero = 1 / matrix.size
    info = matrix.stack().describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])
    info["sum"] = matrix.sum().sum()
    info["zeros"] = (matrix == 0).sum().sum()
    info["almost_zeros"] = (matrix < almost_zero).sum().sum()
    info["NaNs"] = matrix.isna().sum().sum()
    return info
