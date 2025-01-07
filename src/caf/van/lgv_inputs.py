# -*- coding: utf-8 -*-
"""
    Module containing functionality for reading and pre-processing
    the LGV inputs which are used for multiple segments.
"""

##### IMPORTS #####

from __future__ import annotations

# Built-Ins
import datetime as dt
import enum
import logging
from multiprocessing import Value
import re
import string
from pathlib import Path
from typing import Any, Callable, Optional, Literal

# Third Party


import caf.base
import caf.toolkit
import numpy as np
import pandas as pd
from pydantic import dataclasses, fields, model_validator, field_validator, types
from caf.base import DVector, ZoningSystem

# Local Imports
from caf.van import errors, utilities
from caf.van.rezone import Rezone
from caf.van.utilities import DataPaths

##### CONSTANTS #####
LOG = logging.getLogger(__name__)

HH_PROJECTIONS_HEADER = {"Area Description": str, "HHs": float}
"""Column names (and data types) for input CSV to `household_projections` function."""

LGV_PARAMETERS_SHEET = "Parameters"
"""Name of the sheet containing the main LGV parameters."""

LGV_PARAMETERS_COLUMNS = {"Parameter": str, "Value": float}
"""Column names in the `LGV_PARAMETERS_SHEET`."""

LGV_PARAMETERS = {
    "lgv_growth": "LGV growth",
    "avg_new_house_size": "Average new house size",
    "scotland_soc82_ratio": "Scotland SOC821/SOC82",
    "year": "Model Year",
}
"""Names of the parameters (values) expected and their internal code name (keys)."""

TIME_PERIOD_SHEET = "Time Period Factors"
"""Name of the Excel Worksheet containing the time period factors."""

TIME_PERIOD_COLUMNS = {
    "time_period": ("Time Period", str),
    "service": ("Service", float),
    "delivery_parcel_stem": ("Delivery Parcel Stem", float),
    "delivery_parcel_bush": ("Delivery Parcel Bush", float),
    "delivery_grocery": ("Delivery Grocery", float),
    "commuting_drivers": ("Commuting Drivers", float),
    "commuting_skilled_trades": ("Commuting Skilled Trades", float),
    "personal": ("Personal", float),
}
"""Name and dtype of the expected columns in the time period table."""

GM_PARAMS_SHEET = "Gravity Model Parameters"
"""Name of the Excel Worksheet containing the gravity model parameters."""

GM_PARAMS_COLUMNS = {
    "segment": ("Segment", str),
    "furness_type": ("Furness Constraint Type", str),
    "function": ("Cost Function", str),
    "param1": ("Cost Function Parameter 1", float),
    "param2": ("Cost Function Parameter 2", float),
    "calibrate": ("Run Calibration", str),
}
"""Name and dtype of the expected columns in the gravity model parameters table."""

LGV_SEGMENTS = [
    "service",
    "delivery_parcel_stem",
    "delivery_parcel_bush",
    "delivery_grocery",
    "commuting_drivers",
    "commuting_skilled_trades",
]
"Names of the LGV segments."

EXAMPLE_CONFIG_NAME = "LGV_config_example.yml"
"""Name of the example config file to write."""

DEFAULT_PERSONAL_PURPOSES = (3, 4, 5, 6, 7, 8, 13, 14, 15, 16, 18)
"""Default personal purposes to include in the LGV model."""


##### CLASSES #####
@dataclasses.dataclass
class CommuteWarehousePaths:
    """Paths to LSOA warehouse data for the commute segment."""

    medium: types.FilePath
    """Path to the medium weighted warehouse data."""
    low: Optional[types.FilePath] = None
    """Path to the low weighted warehouse data."""
    high: Optional[types.FilePath] = None
    """Path to the high weighted warehouse data."""


@dataclasses.dataclass
class DwellingPaths:
    """Paths to the TfN dwelling CSVs and zone correspondence."""

    occupied: types.FilePath
    """Path to the occupied dwellings data DVector.
    No specific segmentation is required as it is aggregated to total households by zone."""
    zc_path: types.FilePath
    """Path to the zone correspondence CSV."""
    unoccupied: Optional[types.FilePath] = None
    """Path to the unoccupied dwellings data DVector. 
    No specific segmentation is required as it is aggregated to total households by zone."""


@dataclasses.dataclass
class EmploymentPaths:
    """Path to the TfN employment land-use data and zone correspondence."""

    path: types.FilePath
    """Path to the TfN Land-use DVector. Required segmentation is 'sic_1_digit'."""
    zc_path: types.FilePath
    """Path to the zone correspondence CSV."""


@dataclasses.dataclass
class ZoneTranslationDefinition:
    """Contains the path and column names of the zone translation."""

    path: types.FilePath
    """Path to the zone translation CSV."""
    from_zoning: str
    """Name of the zoning to translate from."""
    to_zoning: str
    """Name of the zoning to translate to."""


class LGVInputPaths(caf.toolkit.BaseConfig):
    """Dataclass storing paths to all the input files for the LGV model."""

    zoning: str
    """Name of the zoning system to use for the model."""
    household_paths: DwellingPaths
    """Paths for the households data and zone correspondence."""
    employment_paths: EmploymentPaths
    """Paths to the TfN employment land-use data."""
    warehouse_path: types.FilePath
    """Path for the warehouse floorspace data CSV at LSOA level for the delivery segment."""
    commute_warehouse_paths: CommuteWarehousePaths
    """Paths to the LSOA warehouse data for the commute segment."""
    parameters_path: types.FilePath
    """Path to the LGV parameters Excel workbook."""
    qs606ew_path: types.FilePath
    """Path to the 2011 England & Wales Census Occupation data CSV."""
    qs606sc_path: types.FilePath
    """Path to the 2011 Scottish Census Occupation data CSV."""
    constructions_path: types.FilePath
    """Path to GB construction data csv."""
    lsoa_lookup_path: types.FilePath
    """Path to the LSOA to model zone correspondence CSV."""
    msoa_lookup_path: types.FilePath
    """Path to the MSOA to model zone correspondence CSV."""
    lad_lookup_path: types.FilePath
    """Path to the Local Authority District to model zone correspondence
    CSV"""
    tripend_balancing_regions_path: types.FilePath
    """Path to csv containing trip end balancing regions to zone correspondence"""
    model_study_area: types.FilePath  # TODO(KF) This isnt used - get rid
    """Path to CSV containing lookup for zones in model study area."""
    summary_zone_translation: ZoneTranslationDefinition
    """Path to model zones to summary zones correspondance CSV"""
    cost_matrix_path: types.FilePath
    """Path to CSV containing cost matrix, should be square matrix with
    zone numbers as column names and indices."""
    gm_parameters: dict[str, GMInputs]
    """Dictionary of gravity model parameters for each segment."""
    output_folder: types.DirectoryPath
    """Path to folder to save outputs to."""
    normits_pa_folder: types.DirectoryPath  # keep as is
    """Path to the full PA Normits matrices, should contain all non home
    based and home based matrices"""
    normits_to_msoa_lookup: types.FilePath  #?????
    """Normits to MSOA(NTEM) lookup, this is NorMITs to model zone lookup as the
    results are taken after normits results are converted back to NoHAM"""
    normits_to_personal_factor: float  # keep as is
    """This is the factor that the personal data should have applied to
    just include van data 4% is a starting point"""
    personal_purposes: list[int] = fields.Field(
        default_factory=lambda: list(DEFAULT_PERSONAL_PURPOSES)
    )
    """Personal purpose types defined by Normits"""
    _model_output_folder: Path | None = fields.PrivateAttr(None)

    @property
    def model_output_folder(self) -> Path:
        """Output folder for single run of model."""
        if self._model_output_folder is None:
            self._model_output_folder = (
                self.output_folder
                / f"CAF.Van Model Outputs - {dt.datetime.now():%Y-%m-%d %H.%M.%S}"
            )
            self._model_output_folder.mkdir(exist_ok=True)
        return self._model_output_folder


InfillFunction = Callable[[np.ndarray], float]


class InfillMethod(enum.Enum):
    """Options for filling in NaN values in warehouse data."""

    MIN = "minimum"
    MEAN = "mean"
    MEDIAN = "median"
    NON_ZERO_MIN = "non-zero minimum"
    ZERO = "zero"

    @classmethod
    def method_lookup(cls) -> dict[InfillMethod, InfillFunction]:
        """Lookup for the infill functions."""
        return {
            cls.MIN: np.nanmin,
            cls.MEAN: np.nanmean,
            cls.MEDIAN: np.nanmedian,
            cls.NON_ZERO_MIN: lambda a: np.amin(a, where=a > 0, initial=np.inf),
            cls.ZERO: lambda _: 0,
        }

    def method(self) -> InfillFunction:
        """Function to calculate infilling value."""
        return self.method_lookup()[self]


##### FUNCTIONS #####
def household_projections(
    occupied_paths: Path,
    zone_lookup: Path,
    unoccupied_paths: Optional[Path] = None,
) -> pd.DataFrame:
    """Reads and aggregates the household DVectors and converts to model zone system.

    No specific segmentation is required for the DVectors since the data is aggregated 
    to households per zone.

    Parameters
    ----------
    occupied_paths : Path
        Path to Occupied Dwellings DVector.
    zone_lookup : Path
        Path to the zone correspondence CSV.
    unoccupied_paths : Optional[Path], optional
        Path to Occupied Dwellings DVector. If None then only the occupied dwellings 
        are used to calculate households. None by default.

    Returns
    -------
    pd.DataFrame
        Household projections in the model zone system with columns
        'Zone' and 'Households'.
    """

    zone_correspondence = pd.read_csv(zone_lookup)

    households = (
        DVector.load(occupied_paths)
        .translate_zoning(ZoningSystem.get_zoning("NorMITs"), trans_vector=zone_correspondence)
        .data
    )

    households_agg = households.sum()

    if unoccupied_paths is not None:
        unoccupied = (
            DVector.load(unoccupied_paths)
            .translate_zoning(
                ZoningSystem.get_zoning("NorMITs"), trans_vector=zone_correspondence
            )
            .data
        )
        households_agg = households_agg + unoccupied.sum()

    households_agg = households_agg.to_frame(name="Households")
    households_agg.index.name = "Zone"

    return households_agg


def filtered_employment(
    paths: EmploymentPaths,
    aggregation: dict[str, tuple[int]],
) -> pd.DataFrame:
    """Read and aggregated the TfN employment land-use DVector.

    The DVector should contain the 'sic_1_digit' segmentation, any other segmentation will be
    aggregated.

    Parameters
    ----------
    path : EmploymentPaths
        Contains DVector containing the employment data and the zone correspondence
        between the DVector zoning and the model zoning system.
    aggregation : dict[str, tuple[str]]
        Dictionary containing names of any industry columns
        to aggregate together, the keys should be the name
        of the new column to create and the tuple should
        contain the 'sic_1_digit' IDs to aggregate together
        (ints corresponding to the letter segmentation).

    Returns
    -------
    pd.DataFrame
        TfN Land-Use data with 'sic_1_digit' IDs aggregated and converted
        to the model zone system, contains 'Zone' column with zone
        numbers and then one column per item in `aggregation` (key
        is the column name).
    """
    emp = caf.base.DVector.load(paths.path)

    emp = emp.translate_zoning(
        ZoningSystem.get_zoning("NorMITs"), trans_vector=pd.read_csv(paths.zc_path)
    )
    agg_emp = emp.aggregate(["sic_1_digit"])
    emp_data = agg_emp.data

    code_cat_correspondence = {}
    for replacement, values in aggregation.items():
        for v in values:
            code_cat_correspondence[v] = replacement

    cat_emp_data = emp_data.rename(index=code_cat_correspondence)

    cat_emp_data = cat_emp_data[cat_emp_data.index.isin(aggregation.keys())]

    cat_emp_data = cat_emp_data.groupby("sic_1_digit").sum()

    filtered_employment_data = cat_emp_data.transpose(copy=True)

    return filtered_employment_data


def load_warehouse_floorspace(
    path: Path,
    zone_lookup: Path,
) -> pd.DataFrame:
    """Load warehouse floorspace data and convert to model zone system.

    Parameters
    ----------
    path : Path
        Path to CSV containing warehouse floorspace data with
        columns: "LSOA11CD", "area".
    zone_lookup : Path
        Path to zone correspondence CSV.

    Returns
    -------
    pd.DataFrame
        Warehouse floorspace area by model zone with index ("Zone")
        containing zone ID and column ("area") containing the
        floorspace area.
    """
    lsoa_column = "LSOA11CD"
    area_column = "area"
    floorspace = utilities.read_csv(path, columns={lsoa_column: str, area_column: float})

    lookup = Rezone.read(zone_lookup, None)

    rezoned, _ = Rezone.rezone(floorspace, lookup, lsoa_column, rezoneCols=area_column)
    rezoned.rename(columns={lsoa_column: "Zone"}, inplace=True)
    grouped = rezoned.groupby("Zone").sum()

    grouped = grouped.reindex(lookup["new"].unique())
    return grouped


def lgv_parameters(path: Path) -> dict[str, Any]:
    """Read the LGV Parameters sheet from the Excel workbook.

    Parameters
    ----------
    path : Path
        Path to the Excel workbook containing `LGV_PARAMETERS_SHEET`.

    Returns
    -------
    dict[str, Any]
        Dictionary of all the generic LGV parameters.

    Raises
    ------
    LFT.errors.MissingDataError
        If any expected parameters are missing.

    See Also
    --------
    LGV_PARAMETERS_SHEET
    LGV_PARAMETERS_COLUMNS
    LGV_PARAMETERS
    """
    params = utilities.read_multi_sheets(path, {LGV_PARAMETERS_SHEET: LGV_PARAMETERS_COLUMNS})[
        LGV_PARAMETERS_SHEET
    ]
    params = utilities.to_dict(params, *LGV_PARAMETERS_COLUMNS, name="LGV Parameters")
    missing = []
    out_params = {}
    for key, nm in LGV_PARAMETERS.items():
        try:
            out_params[key] = params[nm]
        except KeyError:
            missing.append(nm)
    if missing:
        raise errors.MissingDataError("LGV Parameters", missing)
    return out_params


def read_study_area(path: Path) -> set:
    """Reads model study area CSV.

    Parameters
    ----------
    path : Path
        Path to CSV containing columns 'zone' and
        'internal'.

    Returns
    -------
    set[int]
        Set of zone numbers for all zones
        inside the study area.

    Notes
    -----
    The CSV should contain two columns:
    - zone: the zone number
    - internal: a value of 1 or 0 for whether
      the zone is in the study area or not

    Any zones not given are assumed to be outside
    the study area.
    """
    columns = {"zone": str, "internal": int}
    df = utilities.read_csv(path, "Model Study Area CSV", columns)
    df.loc[:, "zone"] = pd.to_numeric(df["zone"], downcast="unsigned", errors="ignore")
    df.loc[:, "internal"] = df["internal"].astype(bool)
    internal = df.loc[df.internal, "zone"].tolist()
    return set(internal)


def read_time_factors(path: Path) -> dict[str, dict[str, float]]:
    """Read time period factors from Excel Worksheet.

    Expected worksheet name given by `TIME_PERIOD_SHEET`
    and expected columns given in `TIME_PERIOD_COLUMNS`.

    Parameters
    ----------
    path : Path
        Path to the Excel workbook containing the factors.

    Returns
    -------
    dict[str, dict[str, float]]
        Dictionary of all given time periods which contains
        dictionaries for the factor (value) for each segment
        (key). Keys for the internal dictionary are the same
        as the keys in `TIME_PERIOD_COLUMNS`.
    """
    df = utilities.read_excel(
        path,
        "Time Period Table",
        columns=dict(TIME_PERIOD_COLUMNS.values()),
        sheet_name=TIME_PERIOD_SHEET,
        index_col=0,
    )
    rename = {v[0]: k for k, v in TIME_PERIOD_COLUMNS.items()}
    df.rename(columns=rename, inplace=True)
    return df.to_dict(orient="index")


@dataclasses.dataclass
class GMInputs:
    trip_length_distribution_path: types.FilePath
    cost_function: Literal["log_normal", "tanner"]
    cost_function_params: tuple[float, ...] | dict[str | int, tuple[float, ...]]
    calibrate: bool
    cat_zone_correspondance_path: Optional[types.FilePath] = None
    furness_jacobian: bool = True

    @field_validator("cost_function_params", mode="before")
    @classmethod
    def parse_parameters(
        cls, params: dict[str, str] | str
    ) -> dict[str | int, tuple[float, ...]] | tuple[float, ...]:
        # keys will be read in as strings even if numeric.
        # try converting them to numeric if possible

        if isinstance(params, dict):
            checked_keys = {}
            no_errors = True

            for key, vals in params.items():
                try:
                    checked_keys[int(key)] = vals
                except ValueError:
                    # if one isnt an int we dont convert any
                    no_errors = False
            if no_errors:
                key_checked_params = checked_keys
            else:
                key_checked_params = params

            processed_params = {}
            for key, val in key_checked_params.items():
                split_vals = []
                for v in val.split(","):
                    split_vals.append(float(v))
                processed_params[key] = tuple(split_vals)
            return processed_params
        else:
            assert isinstance(params, str)
            split_vals = []
            for v in params.split(","):
                split_vals.append(float(v))
            return tuple(split_vals)

    @model_validator(mode="after")
    def _check_cost_params(self) -> GMInputs:

        multi_tld = True

        try:
            tld_cats = set(pd.read_csv(self.trip_length_distribution_path)["area"].unique())

        except KeyError:
            if self.cat_zone_correspondance_path is None:
                multi_tld = False
            else:
                raise ValueError(
                    "If cat_zone_correspondance is passed, the area column in"
                    " trip_length_distribution_path, must be defined"
                )

        if isinstance(self.cost_function_params, tuple):
            # if we have a multi TLD and and using run mode (a.k.a. not self.calibrate)
            # then we must have a dictionary
            if multi_tld and not self.calibrate:
                raise KeyError(
                    'if cat_zone_correspondance_path is passed when using "run" mode,'
                    " the cost_function_params must be passed as a dictionary with keys"
                    ' of the unique values in the "area" column in '
                    "cat_zone_correspondance_path and trip_length_distribution_path"
                )
        else:

            assert isinstance(self.cost_function_params, dict)

            correspondance_cats = set(
                pd.read_csv(self.cat_zone_correspondance_path)["area"].unique()
            )

            if tld_cats != correspondance_cats:
                raise KeyError(
                    'the "area" column in cat_zone_correspondance_path and '
                    "trip_length_distribution_path must have the same unique values"
                )

            if tld_cats != set(self.cost_function_params.keys()):
                raise KeyError(
                    'if cat_zone_correspondance_path is passed when using "run" mode,'
                    " the cost_function_params must be passed as a dictionary with keys"
                    ' of the unique values in the "area" column in '
                    "cat_zone_correspondance_path and trip_length_distribution_path"
                )

        return self
