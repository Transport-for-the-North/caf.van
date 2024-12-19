# -*- coding: utf-8 -*-
"""
    Module containing the functionality for matrix furnessing and factoring.

    See Also
    --------
    .gravity_model
"""

##### IMPORTS #####

# Built-Ins
import logging
from dataclasses import dataclass
from enum import Enum, auto

# Third Party
import numpy as np

##### CONSTANTS #####
LOG = logging.getLogger(__name__)


##### CLASSES #####
class FurnessConstraint(Enum):
    """Types of furnessing/factoring for the gravity model."""

    SINGLE = auto()
    DOUBLE = auto()

    def __str__(self):
        return f"{self.__class__.__name__}.{self.name}"

##### FUNCTIONS #####
def _check_matrix(matrix: np.ndarray):
    """Check given `matrix` is square."""
    if matrix.ndim != 2:
        raise ValueError(f"matrix should have 2 dimensions not: {matrix.ndim}")
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"matrix should be a square not shape: {matrix.shape}")


def factor_1d(matrix: np.ndarray, total: np.ndarray, axis: int) -> np.ndarray:
    """Factor the given `axis` of `matrix` to match `total`.

    Parameters
    ----------
    matrix : np.ndarray
        Square matrix to be factored.
    total : np.ndarray
        The totals that the `matrix` should be
        factored to match.
    axis : int
        The axis of `matrix` which should be factored.

    Returns
    -------
    np.ndarray
        The `matrix` after it has been factored.

    Raises
    ------
    ValueError
        If `total` isn't the correct shape or
        `axis` isn't 0 or 1.
    """
    _check_matrix(matrix)
    if total.ndim != 1:
        raise ValueError(f"total should have 1 dimension not: {total.ndim}")
    if len(total) != matrix.shape[0]:
        raise ValueError("total should be the same length as matrix")
    if axis not in (0, 1):
        raise ValueError(f"axis should be 0 or 1 not: {axis}")

    curr_tot = np.sum(matrix, axis=axis)
    # Set factor to 0 wherever curr_tot is zero
    factor = np.divide(
        total, curr_tot, out=np.ones_like(total, dtype=float), where=curr_tot != 0
    )
    if axis == 0:
        # Factoring column totals so multiplying factor by each row
        new_matrix = matrix * factor
    else:
        # Factoring row totals so muliplying factor by each column
        new_matrix = matrix * factor.reshape((len(factor), 1))
    return new_matrix


def factor_totals(
    col_total: np.ndarray, row_total: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Factor column/row total arrays so they have the same total."""
    trip_ends = [col_total, row_total]
    totals = np.sum(trip_ends, axis=1)
    if totals[0] == totals[1]:
        return col_total, row_total
    mean_tot = np.mean([np.sum(col_total), np.sum(row_total)])
    LOG.info("Factoring trip ends sum to mean total: %s", mean_tot)
    new_totals = []
    for tot, arr in zip(totals, trip_ends):
        new_totals.append(arr * mean_tot / tot)
    return tuple(new_totals)


def annual_pa_to_od(
    matrix: np.ndarray, col_total: np.ndarray, row_total: np.ndarray
) -> np.ndarray:
    """Convert annual PA matrix to OD by adding on the transpose after factoring to totals.

    Simple PA to OD conversion by factoring the `matrix` up to
    the `row_total` and factoring the transposed `matrix` to
    the `col_total`, then adding the transposed to `matrix`.
    If the totals are the same then the matrices don't need
    to be factored.

    Parameters
    ----------
    matrix : np.ndarray
        Square annual PA trip matrix.
    col_total : np.ndarray
        Expected column totals.
    row_total : np.ndarray
        Expected row totals.

    Returns
    -------
    np.ndarray
        Matrix after conversion to OD.
    """
    if np.allclose(col_total, row_total):
        return matrix + matrix.T
    col_total, row_total = factor_totals(col_total, row_total)
    matrix = factor_1d(matrix, row_total, 1)
    matrix_t = factor_1d(matrix, col_total, 0).T
    return matrix + matrix_t
