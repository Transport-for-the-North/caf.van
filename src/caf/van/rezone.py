"""
Rezones a matrix when given a lookup with splitting factors.
"""

##### IMPORTS #####

# Built-Ins
import logging
import sys

# Local Imports
from caf.van.errors import IncorrectParameterError, MissingLookupValuesError
from caf.van.utilities import Parameters, read_csv

##### CONSTANTS #####
LOG = logging.getLogger(__name__)


##### CLASS #####
class Rezone:
    """Class for rezoning a matrix when given a lookup with splitting factors."""

    @classmethod
    def read(cls, path, columns):
        """Read the lookup file.

        Parameters
        ----------
        path: str
            Path to the lookup file.
        columns: dict
            Column names in the lookup file should contain 3 keys,
            old, new, splitting_factor. If None then ignores the
            header row and uses the first 3 columns in file as old,
            new and splitting_factor respectively.

        Returns
        -------
        lookup: pandas.DataFrame
            DataFrame object with the old, new and
            splitting_factor columns read from the file.
        """
        # Check columns given
        if columns is None:
            cols = {"old": 0, "new": 1, "splitting_factor": 2}
            rename = list(cols.keys())
        else:
            cols = Parameters.check_params(
                columns, ("old", "new", "splitting_factor"), name="INPUT_COLUMNS"
            )
            rename = {v: k for k, v in cols.items()}

        # Read file checking if there are any format errors
        try:
            df = read_csv(
                path, "Rezoning Lookup", columns=list(cols.values()), low_memory=False
            )
        except IncorrectParameterError:
            err_type, err_val = sys.exc_info()[:2]
            # Log any errors and reraise
            LOG.error("%s: %s", err_type.__name__, str(err_val))
            raise

        # Set column names if rename is list or use rename method with dicts
        if isinstance(rename, (tuple, list)):
            df.columns = rename
        else:
            df.rename(columns=rename, inplace=True)
        return df

    @staticmethod
    def rezone(
        df,
        lookup,
        df_col,
        lookup_old="old",
        lookup_new="new",
        split_col="splitting_factor",
        rezone_cols="trips",
    ):
        """Rezones a dataframe with a lookup dataframe, using splitting factors.

        Parameters
        ----------
        df: pandas.DataFrame
            The matrix to be rezoned.
        lookup: pandas.DataFrame
            The lookup tables to do the rezoning.
        df_col: str
            The column to be replaced with a new zone system.
        lookup_old: str, optional
            The column that contains the current zone system (present in df).
            Default 'old'
        lookup_new: str, optional
            The column that contains the new zone system.
            Default 'new'.
        split_col: str, optional
            The column that contains the splitting factors.
            Default 'splitting_factor'.
        rezone_cols: str or list-like, optional, default "trips"
            The column(s) which should be multiplied by the `splitCol`
            during rezoning.

        Returns
        -------
        merged: DataFrame
            Rezoned input dataframe.
        missing: DataFrame
            Rows containing zones not present in the lookup dataframe
        """
        original_cols = df.columns
        # Join the dfs
        merged = df.merge(
            lookup,
            left_on=df_col,
            right_on=lookup_old,
            how="left",
            indicator=True,
            suffixes=("", "_Lookup"),
        )
        missing = merged.loc[merged["_merge"] != "both"]
        # Set the column to the new zones
        merged[df_col] = merged[lookup_new]
        # Convert the split columns
        if isinstance(rezone_cols, str):
            merged[rezone_cols] = merged[rezone_cols] * merged[split_col]
        else:
            for c in rezone_cols:
                merged[c] = merged[c] * merged[split_col]
        return merged[original_cols], missing

    @classmethod
    def rezone_od(cls, df, lookup, dfCols=("origin", "destination"), **kwargs):
        """Rezones the matrix on both the origin and destination columns.

        Uses the `rezone` method.

        Parameters
        ----------
        df: pandas.DataFrame
            The matrix to be rezoned.
        lookup: pandas.DataFrame
            The lookup tables to do the rezoning.
        dfCols: iterable
            The columns to be replaced with a new zone system.
        kwargs: keyword arguments
            Any keyword arguments to pass to `Rezone.rezone`.

        Returns
        -------
        df: pandas.DataFrame
            The original dataframe with the columns rezoned.
        """
        # Loop through the dfCols
        dfCols = list(dfCols)
        for c in dfCols:
            df, missing = cls.rezone(df, lookup, c, **kwargs)
            # Check if there are any missing lookup values
            if len(missing) > 1:
                missing = missing[c].unique()
                raise MissingLookupValuesError(missing, c)

        # Group the new zones
        df = df.groupby(dfCols, as_index=False).sum()
        return df
