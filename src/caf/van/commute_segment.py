"""
Module to calculate the productions and attractions for the LGV
commuting segment in the model zone system.
"""

from __future__ import annotations

# Built-Ins
import logging
import pathlib
import re
from itertools import chain
from typing import Callable, Optional, Union

# Third Party
import caf.toolkit as ctk
import numpy as np
import pandas as pd
import pydantic

# Local Imports
from caf.van import errors, lgv_inputs, utilities
from caf.van.rezone import Rezone

##### CONSTANTS #####
LOG = logging.getLogger(__name__)
BUSINESS_FLOORSPACE_HEADER: dict[str, type] = {"AREA_CODE": str}
BUSINESS_FLOORSPACE_RENAME = {"AREA_CODE": "zone"}
BUSINESS_CATEGORIES = ["Retail", "Office", "Industrial", "Other"]
BUSINESS_FLOORSPACE_REMOVE_ROWS = ["K", "E9", "W9", "E1"]
E_DWELLINGS_HEADER = [
    "Current\nONS code",
    "Lower and Single Tier Authority Data",
    "Demolitions",
    "Net Additions",
]
E_DWELLINGS_NEW_COLS = {"Current\nONS code": "zone"}

QS606_BASE_HEADERS = {
    "mnemonic": str,
    "All categories: Occupation": float,
    "51. Skilled agricultural and related trades": float,
    "52. Skilled metal, electrical and electronic trades": float,
    "53. Skilled construction and building trades": float,
}
QS606_HEADERS: dict[str, dict[str, type]] = {
    "EW": {**QS606_BASE_HEADERS, "821. Road Transport Drivers": float},
    "SC": {
        **QS606_BASE_HEADERS,
        "82. Transport and mobile machine drivers and operatives": float,
    },
}
QS606_HEADER_FOOTER = {"EW": (8, 5), "SC": (7, 5)}


##### CLASSES #####
class WarehouseParameters(pydantic.BaseModel):
    """Parameters for warehouse data used in commute segment."""

    medium: Optional[float] = pydantic.Field(alias="Weighting - Medium")
    high: Optional[float] = pydantic.Field(alias="Weighting - High")
    low: Optional[float] = pydantic.Field(alias="Weighting - Low")
    zone_infill: list[Union[int, str]] = pydantic.Field(
        alias="Model Zone Infill", default_factory=list
    )
    infill_method: Optional[lgv_inputs.InfillMethod] = pydantic.Field(
        None, alias="Zone Infill Method"
    )

    @pydantic.validator("zone_infill", pre=True)
    def _split_str(cls, value: str) -> list:  # pylint: disable=no-self-argument
        return value.split(",")


class CommuteTripEnds:
    """Functionality for generating the LGV commuting segment trip productions
    and attractions.

    Parameters
    ----------
    inputs : LGVInputPaths
        Dataclass storing paths to all the input files for the LGV model.
    model_zones : pd.Series
        Full list of model zones.

    See Also
    --------
    .lgv_inputs: Module with functions for reading some inputs.
    """

    COMMUTING_INPUTS_SHEET_HEADERS = {
        "Parameters": {"Parameter": str, "Value": float},
        "Commute trips by main usage": {"Main usage": str, "Trips": float},
        "Commute trips by land use": {"Land use at trip end": str, "Trips": float},
        "Commute Warehouse Parameters": {"Parameter": str, "Value": str},
        "Delivery Segment Parameters": {"Parameter": str, "Value": str},
    }

    EMPLOYMENT_AGGREGATION = {
        "Non-Construction": list(
            chain(
                range(1, 6),  # A - E (1-5)
                range(7, 20),  # G - S (7-19)
            )
        )
    }

    HH_PROJECTIONS_HEADER = {"Area Description": str, "HHs": float, "Jobs": float}
    HH_RENAME = {"Area Description": "zone", "HHs": "households", "Jobs": "jobs"}

    def __init__(self, input_paths: lgv_inputs.LGVInputPaths, model_zones: pd.Series):
        """Initialise class by checking all input paths are in input dict and
        all input files exist"""
        self.paths = input_paths
        self.model_zones = model_zones

        self.params: dict[str, float] = {}
        self.warehouse_parameters: WarehouseParameters | None = None
        self.zone_lookups: dict[str, pd.DataFrame] = {}
        self.commute_trips_main_usage = {}
        self.commute_trips_land_use = {}
        self.trip_productions = None
        self.attractor_factors: dict[str, pd.DataFrame] = {}
        self.attraction_functions: dict[str, Callable] = {  # pylint: disable = invalid-name
            "Construction": self._calc_construction_factors,
            "Residential": self._calc_residential_factors,
            "Employment": self._calc_employment_factors,
            "Skilled trades": self._estimate_skilled_attractions,
            "Drivers": self._estimate_driver_attractions,
        }
        self.trip_attractions = None
        self.trip_ends: dict[str, pd.DataFrame] = {}
        self.infill_zones: list[int | str] = []

    @property
    def inputs_summary(self) -> pd.DataFrame:
        """Returns a summary table of class inputs.

        Returns
        -------
        pd.DataFrame
            Summary of inputs
        """
        return pd.DataFrame.from_dict(self.paths.dict(), orient="index", columns=["Path"])

    def _read_commute_tables(self):
        """Read in commuting tables input XLSX."""
        commute_tables = utilities.read_multi_sheets(
            self.paths.parameters_path, sheets=self.COMMUTING_INPUTS_SHEET_HEADERS
        )

        # TODO(MB) Create a pydantic dataclass to store / validate the parameters
        self.params = utilities.to_dict(
            commute_tables["Parameters"], "Parameter", ("Value", float)
        )
        self.params["Model Year"] = int(self.params["Model Year"])

        sheet = "Commute Warehouse Parameters"
        headers = list(self.COMMUTING_INPUTS_SHEET_HEADERS[sheet])
        warehouse_params: pd.Series = commute_tables[sheet].set_index(headers[0])[headers[1]]
        self.warehouse_parameters = WarehouseParameters.parse_obj(warehouse_params.to_dict())

        # write the commute trips by main usage to a dictionary
        commute_trips_main_usage = utilities.to_dict(
            commute_tables["Commute trips by main usage"],
            key_col="Main usage",
            val_col=("Trips", int),
        )
        self.commute_trips_main_usage["Drivers"] = commute_trips_main_usage["G"]
        self.commute_trips_main_usage["Skilled trades"] = (
            commute_trips_main_usage["S"] + commute_trips_main_usage["C"]
        )

        self.commute_trips_main_usage = {
            k: v * self.params["LGV growth"] for k, v in self.commute_trips_main_usage.items()
        }
        LOG.info("Grown commute trips main usage: %s", self.commute_trips_main_usage)

        self.commute_trips_land_use = utilities.to_dict(
            commute_tables["Commute trips by land use"],
            key_col="Land use at trip end",
            val_col=("Trips", int),
        )

        self.commute_trips_land_use = {
            k: v * self.params["LGV growth"] for k, v in self.commute_trips_land_use.items()
        }
        LOG.info("Grown commute trips land use: %s", self.commute_trips_land_use)

    def _read_zone_lookups(self):
        for key, value in self.paths.dict().items():
            if value is None:
                continue
            key = key.lower()
            if key.endswith("lookup") or key.endswith("lookup_path"):
                name = re.sub(r"[\s_]+|path", " ", key).strip()
                self.zone_lookups[name] = Rezone.read(value, None)

    def _read_qs606(self):
        """Read in and rezone Census occupation data."""
        # If haven't yet read in parameters and zone lookups, read in
        if not self.params:
            self._read_commute_tables()

        if not self.zone_lookups:
            self._read_zone_lookups()

        qs606 = read_qs606(self.paths.qs606ew_path, self.paths.qs606sc_path)

        # Scottish data doesn't include SOC821, so calculate from SOC82
        qs606["SC"]["821"] = qs606["SC"]["82"] * self.params["Scotland SOC821/SOC82"]

        # Combine the data for England, Wales and Scotland
        qs606uk = pd.concat([qs606["EW"], qs606["SC"].drop(axis=1, labels=["82"])])

        # Combine columns into skilled trades (SOC51, 52, 53) and drivers (SOC821)
        qs606uk["Skilled trades"] = qs606uk[
            [col for col in qs606uk.columns if col.startswith("5")]
        ].sum(axis=1)
        qs606uk = qs606uk.rename(columns={"821": "Drivers"})
        qs606uk = qs606uk[["zone", "total", "Skilled trades", "Drivers"]]

        # Rezone to model zone system
        cols = qs606uk.columns
        return Rezone.rezone_od(
            qs606uk,
            self.zone_lookups["lsoa lookup"],
            df_cols=(cols[0],),
            rezone_cols=cols[1:],
        )

    def _calc_construction_factors(self):
        """Calculates the total change in sqm in residential and business
        floorspace and uses it to calculate construction attractor factors

        We calculate total builds as net additional dwellings +
        2*demolitions as for net dwellings to be >= 0 each demolished
        building needs to be replaces (only true if additional dwellings >=0)
        """
        # get residential floorspace
        construction = ctk.io.read_csv(
            self.paths.constructions_path,
            index_col="zone",
            usecols=[
                "zone",
                "demolished_dwellings",
                "additional_dwellings",
                "business_floorspace",
            ],
        )

        if (construction["demolished_dwellings"] < 0).any():
            raise ValueError(
                "Demolitions smaller than 0 were found in the construction data. "
                "these are not allowed!"
            )

        # we want to raise an error if
        # (additonal dwellings < 0) AND (|additonal dwelling| > demolished dwellings)
        # which is equivelent below. We do this as otherwise we will end up with negative builds,
        # which makes no sense
        if (
            (-construction["additional_dwellings"]) > construction["demolished_dwellings"]
        ).any():
            raise ValueError(
                "Zones with negative additional dwellings must have enough demolitions"
                " to account for the net drop in dwellings"
            )

        construction["total_resi_builds"] = construction["additional_dwellings"] + (
            2 * construction["demolished_dwellings"]
        )

        # we should have caught all possibilities that would happen above
        # BUT I'm prety stupid - so this is here just in case
        if (construction["total_resi_builds"] < 0).any():
            raise ValueError(
                "total residential build has atleast one negative value. Please review"
                " constructions inputs total residential build = additional "
                "dwellings[this is net value] + 2 x demolished dwellings"
            )

        construction["residential_floorspace"] = (
            construction["total_resi_builds"] * self.params["Average new house size"]
        )

        floorspace = (
            construction["business_floorspace"] + construction["residential_floorspace"]
        ).to_frame(name="floorspace")

        self.attractor_factors["Construction"] = (floorspace / floorspace.sum()).rename(
            columns={"floorspace": "factor"}
        )

    def _calc_residential_factors(self):
        """Calculates residential attractor factors from TEMPro households
        data.
        """

        households = lgv_inputs.household_projections(
            self.paths.household_paths.occupied,
            self.paths.household_paths.zc_path,
            self.paths.household_paths.unoccupied,
        )
        households["factor"] = households["Households"] / households["Households"].sum()
        self.attractor_factors["Residential"] = households[["factor"]]

    def _calc_employment_factors(self):
        """Calculates employment attractor factors from employment data"""
        if not self.zone_lookups:
            self._read_zone_lookups()
        employment = lgv_inputs.filtered_employment(
            self.paths.employment_paths, self.EMPLOYMENT_AGGREGATION
        )
        employment["factor"] = (
            employment[self.EMPLOYMENT_AGGREGATION.keys()]
            / employment[self.EMPLOYMENT_AGGREGATION.keys()].sum()
        )
        self.attractor_factors["Employment"] = employment[["factor"]]

    def estimate_productions(self):
        """Reads in files and estimates trip productions by zone and employment
        segment"""
        qs606uk = self._read_qs606()
        # TODO(MB) review calc to check for 1/3

        # Calculate total occupation numbers for Skilled trades and Drivers
        totals = qs606uk.drop(axis=1, labels=["zone", "total"]).sum()

        # Create trip productions df
        self.trip_productions = qs606uk[["zone"]]

        # perform trip production calculation
        for occupation in self.commute_trips_main_usage:
            self.trip_productions.loc[:, occupation] = (
                0.5
                * qs606uk.loc[:, occupation]
                * self.commute_trips_main_usage[occupation]
                / totals[occupation]
            )

        self.trip_productions.index = self.trip_productions["zone"]
        self.trip_productions.drop(columns=["zone"], inplace=True)
        self.trip_productions["Total"] = self.trip_productions.sum(axis=1)

    def _estimate_skilled_attractions(self):
        """Estimates trip attractions for skilled trades.

        Returns
        -------
        pd.DataFrame
            DataFrame of trip attractions with zones as indices and a "trips"
            column.
        """
        # check for commute trip data by land use at trip end
        if not self.commute_trips_land_use:
            self._read_commute_tables()

        # check for any missing attractor factors
        factors_missing = [
            x for x in self.commute_trips_land_use if x not in self.attractor_factors
        ]
        if factors_missing:
            for category in factors_missing:
                self.attraction_functions[category]()

        # calculate skilled attractions, using just residential and construction
        # because employment is used for drivers
        skilled_attractions = {}
        for key in ["Residential", "Construction"]:
            skilled_attractions[key] = (
                self.commute_trips_land_use[key] * self.attractor_factors[key]
            )

        skilled_attractions = sum(skilled_attractions.values()).rename(
            columns={"factor": "trips"}
        )

        return skilled_attractions

    def _estimate_driver_attractions(self):
        """Estimates trip attractions for Drivers

        Returns
        -------
        pd.DataFrame
            DataFrame of trip attractions with zones as indices and a "trips"
            column.
        """
        if self.warehouse_parameters is None:
            self._read_commute_tables()

        data_paths = [
            (
                "medium",
                self.paths.commute_warehouse_paths.medium,
                self.warehouse_parameters.medium,
            ),
            ("low", self.paths.commute_warehouse_paths.low, self.warehouse_parameters.low),
            ("high", self.paths.commute_warehouse_paths.high, self.warehouse_parameters.high),
        ]
        factored_data = []

        for name, path, weight in data_paths:
            if path is None and name == "medium":
                raise errors.MissingInputsError("commute warehouse path (medium)")
            if path is None:
                continue
            if weight is None:
                raise errors.MissingInputsError(f"commute warehouse {name} weighting factor")

            data = lgv_inputs.load_warehouse_floorspace(path, self.paths.lsoa_lookup_path)
            data = data * weight
            factored_data.append(data)

        warehouse_floorspace = pd.concat(factored_data, axis=1)

        # Sum will fill Nans with 0 but we need to keep Nan in rows which are all Nan for infilling
        all_nans: pd.Series = warehouse_floorspace.isna().all(axis=1)
        warehouse_floorspace: pd.Series = warehouse_floorspace.sum(axis=1, skipna=True)
        warehouse_floorspace.loc[all_nans] = np.nan

        if self.warehouse_parameters.zone_infill and all_nans.sum() > 0:
            if self.warehouse_parameters.infill_method is None:
                raise ValueError(
                    f"{len(self.warehouse_parameters.zone_infill)} zones "
                    "provided for infilling but no infill method is given"
                )

            infill_function = self.warehouse_parameters.infill_method.method()
            infill_value = infill_function(warehouse_floorspace.dropna().values)

        else:
            infill_value = 0

        warehouse_floorspace = warehouse_floorspace.fillna(infill_value)

        trips = (
            warehouse_floorspace / warehouse_floorspace.sum()
        ) * self.commute_trips_land_use["Employment"]

        return trips.to_frame("trips")

    def estimate_attractions(self):
        """Estimates trip attractions"""
        if not self.commute_trips_main_usage:
            self._read_commute_tables()

        trip_attractions = {}
        for category in self.commute_trips_main_usage:
            trip_attractions[category] = self.attraction_functions[category]()

        # align matrices
        (
            trip_attractions["Drivers"],
            trip_attractions["Skilled trades"],
        ) = trip_attractions["Drivers"].align(
            trip_attractions["Skilled trades"], join="outer", fill_value=0
        )

        self.trip_attractions = sum(trip_attractions.values()).rename(
            columns={"trips": "Total"}
        )
        for col in trip_attractions:
            self.trip_attractions[col] = trip_attractions[col]["trips"]

    def calc_trip_ends(self):
        """Takes production and attraction dataframes with skilled trades and
        drivers as columns and zones as indices and creates skilled trade and
        driver trip dataframes with productions and attractions as columns and
        zones as indices.
        """
        if self.trip_productions is None:
            self.estimate_productions()
        if self.trip_attractions is None:
            self.estimate_attractions()
        for soc in ["Skilled trades", "Drivers"]:
            self.trip_ends[soc] = pd.concat(
                [
                    self.trip_productions[soc],
                    self.trip_attractions[soc],
                ],
                axis=1,
            )
            self.trip_ends[soc].columns = ["Productions", "Attractions"]

            self.trip_ends[soc] = self.trip_ends[soc].reindex(
                index=pd.Index(self.model_zones), fill_value=0
            )

    @property
    def productions(self) -> pd.DataFrame:
        """pd.DataFrame : Trip productions for each zone (index) and
        with columns Total, Skilled trades and Drivers
        """
        if self.trip_productions is None:
            self.estimate_productions()
        return self.trip_productions

    @property
    def attractions(self) -> pd.DataFrame:
        """pd.DataFrame : Trip productions for each zone (index) and
        with columns Total, Skilled trades and Drivers
        """
        if self.trip_attractions is None:
            self.estimate_attractions()
        return self.trip_attractions

    @property
    def trips(self) -> dict[str, pd.DataFrame]:
        """Dict[pd.DataFrame] : dictionary with keys Skilled trades and
        Drivers, with values being the trip dataframes, each with productions
        and attractions as columns and zones as indices."""
        if not self.trip_ends:
            self.calc_trip_ends()
        return self.trip_ends


##### FUNCTIONS #####
def read_qs606(
    ew_path: pathlib.Path, sc_path: pathlib.Path, rename: bool = True
) -> dict[str, pd.DataFrame]:
    """ "Read occupation data."""

    def rename_cols(name: str) -> str:
        """Renames the occupation data columns"""
        match = re.match("^(5[1-3])|(82)[1]?", name)
        if match:
            return match.group(0)
        if name.startswith("mnemonic"):
            return "zone"
        if name.startswith("All"):
            return "total"
        return name

    qs606: dict[str, pd.DataFrame] = {}
    for key, path in (("EW", ew_path), ("SC", sc_path)):
        qs606[key] = (
            utilities.read_csv(
                path,
                columns=QS606_HEADERS[key],
                skiprows=QS606_HEADER_FOOTER[key][0],
                skipfooter=QS606_HEADER_FOOTER[key][1],
                engine="python",
            )
            .dropna(axis=1, how="all")
            .dropna(axis=0, how="any")
        )

        if rename:
            qs606[key] = qs606[key].rename(columns=rename_cols)

    return qs606
