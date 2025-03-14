# -*- coding: utf-8 -*-
"""
    Module for running the LGV model.
"""

##### IMPORTS #####

# Built-Ins
import argparse
import io
import logging
import pprint
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

# Third Party
import caf.distribute.gravity_model
import caf.distribute.gravity_model.multi_area
import numpy as np
import pandas as pd
from caf.distribute import cost_functions, gravity_model

# Local Imports
from caf.van.commute_segment import CommuteTripEnds
from caf.van.delivery_segment import DeliveryTripEnds
from caf.van.lgv_inputs import (
    GMInputs,
    LGVInputPaths,
    lgv_parameters,
    read_study_area,
    read_time_factors,
)
from caf.van.matrix_validation import MatrixReport
from caf.van.rezone import Rezone
from caf.van.service_segment import ServiceTripEnds
from caf.van.utilities import DataPaths, read_csv, read_excel

##### CONSTANTS #####
LOG = logging.getLogger(__name__)
TRIP_DISTRIBUTION_SHEETS = {
    "service": "Service",
    "delivery_parcel_stem": "Delivery",
    "delivery_parcel_bush": "Delivery Bush",
    "delivery_grocery": "Delivery Bush",
    "commuting_drivers": "Commuting",
    "commuting_skilled_trades": "Commuting",
}
"""Name of sheet in trip distributions file for each segment."""

PA_MATRICES = [
    "service",
    "delivery_parcel_stem",
    "commuting_drivers",
    "commuting_skilled_trades",
]
"""List of matrices which are in PA format and will be converted to OD."""

NTEM_PURPOSES = {"hb": list(range(1, 9)), "nhb": [12, 13, 14, 15, 16, 18]}
"""NTEM purpose to hb/nhb correspondence."""

PERSONAL_TIME_PERIODS = [1, 2, 3, 4]
"""Time periods to aggregate NHB together."""

TRIP_DISTRIBUTION_COLS = dict.fromkeys(
    ("start", "end", "average", "observed proportions"), float
)
"""Names and dtypes of the columns expected in the trip distributions input."""

FUNCTION_LABELS = {
    "log_normal": r"Log Normal: $\sigma={:.1e}$, $\mu={:.1e}$",
    "tanner": r"Tanner: $\alpha={:.1e}$, $\beta={:.1e}$",
}
"""Labels for the cost functions in the gravity model."""

"""Definitions """
PA_DIFFERENCE_TOL = 1e-3
"""Tolerance for difference in productions and attractions."""

DUMMY_CAT = 1
"""Label to use when no category is given for the zones/tlds for the gravity model."""


##### CLASSES #####
@dataclass
class LGVTripEnds:
    """Dataclass to store the trip end data for all segments.

    Aligns all the trip end matrices to include all zones
    present in at least one DataFrame, any missing zones
    are filled with 0 trip ends for that DataFrame.
    """

    service: pd.DataFrame
    """Service Productions and Attractions trip ends
    (columns) for all zones (index).
    """
    delivery_parcel_stem: pd.DataFrame
    """Delivery parcel stem Productions and Attractions
    trip ends (columns) for all zones (index).
    """
    delivery_parcel_bush: pd.DataFrame
    """Delivery parcel bush Origins and Destinations
    trip ends (columns) for all zones (index).
    """
    delivery_grocery: pd.DataFrame
    """Delivery grocery bush Origins and Destinations
    trip ends (columns) for all zones (index).
    """
    commuting_drivers: pd.DataFrame
    """Commuting Productions and Attractions trip ends (columns) for Drivers
    (SOC821) for all zones (index).
    """
    commuting_skilled_trades: pd.DataFrame
    """Commuting Productions and Attractions trip ends (columns) for Skilled
    trades (SOCs 51, 52, 53) for all zones (index).
    """
    zones: np.ndarray = field(init=False)
    """Array of all zones, used as index for all trip end dataframes."""

    def __post_init__(self):
        """Reindex all trip end dataframes to contain all zones."""
        dataframes = (
            "service",
            "delivery_parcel_stem",
            "delivery_parcel_bush",
            "delivery_grocery",
            "commuting_drivers",
            "commuting_skilled_trades",
        )
        index = pd.Index([], dtype=int)
        for nm in dataframes:
            index = index.union(getattr(self, nm).index)
        self.zones = index.values
        for nm in dataframes:
            df = getattr(self, nm).reindex(index, fill_value=0)
            # Fill any other NaNs with 0s
            df.fillna(0, inplace=True)
            setattr(self, nm, df)

    def asdict(self) -> dict[str, pd.DataFrame]:
        """Return copies of class attributes as a dictionary."""
        attrs = (
            "service",
            "delivery_parcel_stem",
            "delivery_parcel_bush",
            "delivery_grocery",
            "commuting_drivers",
            "commuting_skilled_trades",
            "zones",
        )
        return {a: getattr(self, a).copy() for a in attrs}

    def __str__(self) -> str:
        msg = [f"{self.__class__.__name__}("]
        for attr in self.asdict():
            if attr == "zones":
                val = getattr(self, attr)
                msg.append(f"{attr}={type(val)}<length {len(val)}><dtype {val.dtype}>")
                continue
            buf = io.StringIO()
            getattr(self, attr).info(buf=buf)
            msg.append(f"{attr}=" + buf.getvalue().replace("\n", "\n\t\t").strip())
        return "\n\t".join(msg) + "\n)"

    def __repr__(self) -> str:
        return str(self)


@dataclass
class LGVMatrices:
    """Dataclass to store the trip matrices for all segments.

    Aligns all the trip matrices to include all zones present
    in at least one DataFrame, any missing zones are filled
    with 0 trips for that DataFrame. Calculates `combined`
    matrix by summing the individual segment matrices.
    """

    service: pd.DataFrame
    """Service trips matrix, with zone numbers
    for columns and indices."""
    delivery_parcel_stem: pd.DataFrame
    """Delivery parcel stem trips matrix, with zone numbers
    for columns and indices."""
    delivery_parcel_bush: pd.DataFrame
    """Delivery parcel bush trips matrix, with zone numbers
    for columns and indices."""
    delivery_grocery: pd.DataFrame
    """Delivery grocery bush trips matrix, with zone numbers
    for columns and indices."""
    commuting_drivers: pd.DataFrame
    """Commuting drivers (SOC821) trips matrix, with zone numbers
    for columns and indices."""
    commuting_skilled_trades: pd.DataFrame
    """Commuting skilled trades (SOCs 51, 52, 53) trips matrix,
    with zone numbers for columns and indices."""
    personal: pd.DataFrame | None = None
    """Contains personal trip matrix outputs from normits,
    with zone numbers for columns and indices"""
    combined: pd.DataFrame = field(init=False)
    """Trips matrix for all combined segments, with zone numbers
    for columns and indices."""
    zones: np.ndarray = field(init=False)
    """Array of all zones, used as index for all trip end dataframes."""

    def __post_init__(self):
        """Reindex all trip end dataframes to contain all zones.

        Sum invidual matrices together to get `combined` matrix.
        """
        dataframes = (
            "service",
            "delivery_parcel_stem",
            "delivery_parcel_bush",
            "delivery_grocery",
            "commuting_drivers",
            "commuting_skilled_trades",
        )
        if self.personal is not None:
            dataframes += ("personal",)
        index = pd.Index([], dtype=int)
        for nm in dataframes:
            index = index.union(getattr(self, nm).index)
            index = index.union(getattr(self, nm).columns)
        self.zones = index.values
        for nm in dataframes:
            df = getattr(self, nm).reindex(index, fill_value=0)
            df = df.reindex(index, axis=1, fill_value=0)
            # Fill any other NaNs with 0s
            df.fillna(0, inplace=True)
            setattr(self, nm, df)
        self.combined = (
            self.service
            + self.delivery_parcel_stem
            + self.delivery_parcel_bush
            + self.delivery_grocery
            + self.commuting_drivers
            + self.commuting_skilled_trades
            + self.personal
        )
        if self.personal is not None:
            self.combined += self.personal

    def asdict(self) -> dict[str, pd.DataFrame]:
        """Return copies of class attributes as a dictionary."""
        attrs = (
            "service",
            "delivery_parcel_stem",
            "delivery_parcel_bush",
            "delivery_grocery",
            "commuting_drivers",
            "commuting_skilled_trades",
            "personal",
            "combined",
            "zones",
        )
        return {a: getattr(self, a).copy() for a in attrs}

    def __str__(self) -> str:
        msg = f"{self.__class__.__name__}("
        ls = []
        for nm, df in self.asdict().items():
            ls.append(f"{nm}=Matrix{df.shape}")
        msg += ", ".join(ls)
        msg += ")"
        return msg

    def __repr__(self) -> str:
        return str(self)


##### FUNCTIONS #####
def calculate_trip_ends(
    input_paths: LGVInputPaths,
    output_folder: Path,
    lgv_growth: float,
    year: int,
) -> LGVTripEnds:
    """Calculates the LGV trip ends for all segments.

    Parameters
    ----------
    input_paths : LGVInputPaths
        Paths to all the input files.
    output_folder : Path
        Path to folder to save trip ends to.
    lgv_growth : float
        Model year LGV growth factor.
    year : int
        Model year.

    Returns
    -------
    LGVTripEnds
        Trip end dataframes for each segment.

    See Also
    --------
    .service_segment.ServiceTripEnds: Calculates service trip ends.
    .delivery_segment.DeliveryTripEnds: Calculates delivery trip ends.
    LGVTripEnds: Stores all trip end DataFrames.
    """
    output_folder.mkdir(exist_ok=True)

    model_zones: pd.Series = pd.read_csv(input_paths.model_zones, usecols=["zone"])["zone"]
    model_zones.name = "Zone"

    if input_paths.tripend_balancing_regions_path is not None:
        regions = pd.read_csv(input_paths.tripend_balancing_regions_path)
    else:
        regions = None

    LOG.info("Calculating Service trip ends")
    service = ServiceTripEnds(
        input_paths.household_paths,
        input_paths.employment_paths,
        input_paths.parameters_path,
        lgv_growth,
        model_zones,
        input_paths.zoning,
    )
    service.read()

    # Calculate the delivery trip ends and save outputs
    LOG.info("Calculating Delivery trip ends")
    delivery = DeliveryTripEnds(
        DataPaths(
            "LGV Delivery Warehouse", input_paths.warehouse_path, input_paths.lsoa_lookup_path
        ),
        input_paths.employment_paths,
        input_paths.household_paths,
        input_paths.parameters_path,
        year,
        model_zones,
    )
    delivery.read()

    # Calculate commuting trip ends and save output
    LOG.info("Calculating Commuting trip ends")
    commute = CommuteTripEnds(input_paths, model_zones)
    commute_trips = commute.trips
    for key in commute_trips:
        commute_trips[key].to_csv(output_folder / Path(f"commute_{key}_trip_ends.csv"))

    # if balancing regions aren't given,
    # we create a lookup from all zones to 1 area to balance to trip end totals
    if regions is None:
        regions = model_zones.to_frame("zone_id")
        regions["area"] = DUMMY_CAT

    # To avoid MyPy whinging
    assert isinstance(regions, pd.DataFrame)

    LOG.info("Balancing Trip Ends")
    service_te = balance_trip_ends(
        service.trip_ends, regions, "Productions", "Attractions", "Service"
    )
    delivery_parcel_stem_te = balance_trip_ends(
        delivery.parcel_stem_trip_ends,
        regions,
        "Productions",
        "Attractions",
        "Delivery Parcel Stem",
    )
    delivery_parcel_bush_te = balance_trip_ends(
        delivery.parcel_bush_trip_ends,
        regions,
        "Origins",
        "Destinations",
        "Parcel Bush Trip Ends",
    )
    delivery_grocery_bush_te = balance_trip_ends(
        delivery.grocery_bush_trip_ends,
        regions,
        "Origins",
        "Destinations",
        "Grocery Bush Trip Ends",
    )
    commute_drivers = balance_trip_ends(
        commute_trips["Drivers"],
        regions,
        "Productions",
        "Attractions",
        "Commuting Drivers",
    )
    commute_skilled_trades = balance_trip_ends(
        commute_trips["Skilled trades"],
        regions,
        "Productions",
        "Attractions",
        "Skilled Trades",
    )

    service_te.to_csv(output_folder / "service_trip_ends.csv")
    delivery_parcel_stem_te.to_csv(output_folder / "delivery_parcel_stem_trip_ends.csv")
    delivery_parcel_bush_te.to_csv(output_folder / "delivery_parcel_bush_trip_ends.csv")
    delivery_grocery_bush_te.to_csv(output_folder / "delivery_grocery_trip_ends.csv")
    commute_drivers.to_csv(output_folder / "commute_drivers_trip_ends.csv")
    commute_skilled_trades.to_csv(
        output_folder / Path(f"commute_skilled_trades_trip_ends.csv")
    )

    LOG.info("\tDone with trip ends")
    return LGVTripEnds(
        service=service_te,
        delivery_parcel_stem=delivery_parcel_stem_te,
        delivery_parcel_bush=delivery_parcel_bush_te,
        delivery_grocery=delivery_grocery_bush_te,
        commuting_drivers=commute_drivers,
        commuting_skilled_trades=commute_skilled_trades,
    )


def balance_trip_ends(
    trip_ends: pd.DataFrame,
    regions: pd.DataFrame,
    control_col: str,
    variable_col: str,
    name: str,
) -> pd.DataFrame:

    # Create a copy so we don't change anything out of function scope
    balanced_trip_ends = trip_ends.copy()

    # check all zones are in the region correspondence
    if trip_ends.index.isin(~regions["zone_id"]).any():
        raise KeyError(
            "Trip Ends Balancing Regions have zones missing when compared to trip ends"
        )

    # iterate through unique areas (we dont care what the areas are, just want the zones within each)
    for r in regions["area"].sort_values().unique():
        # Get the zones we want to balance
        zones = regions.loc[regions["area"] == r, "zone_id"]

        # calculate difference between control and variable columns
        trip_end_difference = (
            balanced_trip_ends.loc[zones, control_col].sum()
            - balanced_trip_ends.loc[zones, variable_col].sum()
        )

        if np.abs(trip_end_difference) > PA_DIFFERENCE_TOL:
            # calculate factor needed to make variable sum equal control sum
            factor = (
                balanced_trip_ends.loc[zones, control_col].sum()
                / balanced_trip_ends.loc[zones, variable_col].sum()
            )
            # apply factor
            balanced_trip_ends.loc[zones, variable_col] *= factor
            LOG.warning(
                f"{control_col} and {variable_col} are imbalanced in for"
                f" {name} region {r} (difference= {trip_end_difference})."
                f" Factoring {variable_col} to {control_col} (factor = {factor})"
            )

        else:
            LOG.info(
                f"Trip ends for {name}: {r} look fine -- difference: {trip_end_difference}"
            )
    return balanced_trip_ends


class VanGravityModelResults:
    """Results from a run of the gravity model.

    Parameters
    ----------
    distribution
        Matrix containing the final distribution of trips,
        will have same number of columns and rows equal to
        the number of `zones`.
    zones
        List of all the zones contained within the matrix,
        the order is the same as in the matrix.
    info
        Gravity model results for each area.
    """

    distribution: pd.DataFrame
    """Matrix containing final distribution of trips, with columns
    and index equal to `zones`."""
    summary: pd.DataFrame
    """Summary of gravity model results for each area."""
    zones: np.ndarray
    """List of all the zones in the `distribution`."""
    info: dict[str | int, gravity_model.GravityModelResults]
    """Gravity model results for each area."""

    def __init__(
        self,
        distribution: np.ndarray,
        zones: np.ndarray,
        info: dict[str | int, gravity_model.GravityModelResults],
    ):

        self.distribution = pd.DataFrame(distribution, index=zones, columns=zones)
        self.zones = zones
        self.info = info

        summary_build = {}
        for key, results in info.items():
            summary_build[key] = results.summary

        self.summary = pd.DataFrame(summary_build).transpose()


def _gravity_model(
    trip_ends: pd.DataFrame,
    name: str,
    gm_data: GMInputs,
    cost_matrix: pd.DataFrame,
    calibrate: bool,
    csv_logging_path: Path,
) -> VanGravityModelResults:
    """Internal function used in `run_gravity_model` for running the GM with calibration."""

    trip_ends = trip_ends.rename(
        columns={
            **dict.fromkeys(("Productions", "Origins"), "row_targets"),
            **dict.fromkeys(("Attractions", "Destinations"), "col_targets"),
        }
    )

    tld_path = gm_data.trip_length_distribution_path

    # we have to do this because caf distribute does not look at index values, just order.
    trip_ends = trip_ends.sort_index()

    # define zones to order everthing on from the ordered trip end index.
    if trip_ends.index.has_duplicates:
        raise KeyError("Trip ends have duplicated zones labels. Please fix this")

    zones = trip_ends.index.to_numpy()
    cost_matrix_validated = cost_matrix.loc[zones, zones].to_numpy()

    LOG.info("Running Gravity Model: %s, with calibration %s", name, calibrate)

    tld = pd.read_csv(tld_path)

    # Use cat zone lookup if it exists.
    if gm_data.cat_zone_correspondance_path is not None:
        cat_zone_correspondence = pd.read_csv(gm_data.cat_zone_correspondance_path)
    else:
        # If not, create a correspondence for all zones to one area i.e. run a single TLD gravity model.
        cat_zone_correspondence = pd.DataFrame({"zone_id": zones})
        cat_zone_correspondence["area"] = DUMMY_CAT
        tld["area"] = DUMMY_CAT

    # Define the cost function and parameters
    if gm_data.cost_function == "log_normal":
        cost_function = cost_functions.BuiltInCostFunction.LOG_NORMAL.get_cost_function()
    elif gm_data.cost_function == "tanner":
        cost_function = cost_functions.BuiltInCostFunction.TANNER.get_cost_function()
    else:
        raise NotImplementedError(
            f"cost function {gm_data.cost_function} is not implemented, please use either log_normal "
            "(mu, sigma) or tanner (alpha, beta)"
        )

    func_params = {}
    if isinstance(gm_data.cost_function_params, dict):
        for cat, params in gm_data.cost_function_params.items():
            func_params[cat] = extract_cost_func_params(params, gm_data.cost_function)
    else:
        # process params when they are a tuple
        for cat in tld["area"].unique():
            func_params[cat] = extract_cost_func_params(
                gm_data.cost_function_params, gm_data.cost_function
            )

    cost_distributions = gravity_model.MultiCostDistribution.from_pandas(
        pd.Series(zones),
        tld,
        cat_zone_correspondence,
        func_params,
        tld_cat_col="area",
        tld_min_col="from",
        tld_max_col="to",
        tld_avg_col="av_distance",
        tld_trips_col="normalised",
        lookup_cat_col="area",
        lookup_zone_col="zone_id",
    )

    calib_gm = gravity_model.MultiAreaGravityModelCalibrator(
        trip_ends["row_targets"].to_numpy(),
        trip_ends["col_targets"].to_numpy(),
        cost_matrix_validated,
        cost_function,
    )

    if calibrate:
        gravity_model_results = calib_gm.calibrate(
            cost_distributions,
            csv_logging_path,  # TODO figure out which key word args with default values needed to be changed
            caf.distribute.gravity_model.multi_area.GMCalibParams(
                furness_jac=gm_data.furness_jacobian
            ),
            verbose=2,
        )

        results = VanGravityModelResults(
            calib_gm.achieved_distribution, zones, gravity_model_results
        )

    else:

        gravity_model_results = calib_gm.run(cost_distributions, csv_logging_path)

        results = VanGravityModelResults(
            calib_gm.achieved_distribution, zones, gravity_model_results
        )
    LOG.info("\tFinished, now writing outputs")
    return results


def extract_cost_func_params(
    cost_funct_params: tuple[float, ...], cost_func_name: Literal["log_normal", "tanner"]
) -> dict[str, float]:
    """Extracts the cost function parameters from a tuple.

    Parameters
    ----------
    cost_funct_params : tuple[float, ...]
        Ordered parameters for the cost function.
    cost_func_name : Literal["log_normal", "tanner"]
        Name of the cost function.

    Returns
    -------
    dict[str, float]
        Unpacked cost function parameters.

    Raises
    ------
    ValueError
        If the cost function name is not recognised.
    """
    if cost_func_name == "log_normal":

        func_params = {
            "mu": cost_funct_params[0],
            "sigma": cost_funct_params[1],
        }
    elif cost_func_name == "tanner":
        func_params = {
            "alpha": cost_funct_params[0],
            "beta": cost_funct_params[1],
        }
    else:
        raise ValueError(f"Cost Function {cost_func_name} not found")

    return func_params


def run_gravity_model(
    input_paths: LGVInputPaths,
    trip_ends: LGVTripEnds,
    output_folder: Path,
) -> dict[str, pd.DataFrame]:
    """Run the gravity model calibration for each segment.

    Parameters
    ----------
    input_paths : LGVInputPaths
        Paths to all inputs files.
    trip_ends : LGVTripEnds
        Trip ends for each segment.
    output_folder : Path
        Path to folder to save outputs.

    Returns
    -------
    dict[str, pd.DataFrame]
        Trip matrices for each segment.
    """
    matrices: dict[str, pd.DataFrame] = {}
    output_folder.mkdir(exist_ok=True)

    cost_matrix = pd.read_csv(input_paths.cost_matrix_path, index_col=0)
    # Pandas casts column names to str, even if theyre numerical (I can't find a parameter to change this)
    # therefore we try to convert to ints
    try:
        cost_matrix.columns = [int(x) for x in cost_matrix.columns]

    # This is for the case where they are strings
    except ValueError:
        pass

    for name, te in trip_ends.asdict().items():

        if name == "zones":
            continue

        gm_params = input_paths.gm_parameters[name]
        calibrate = gm_params.calibrate
        calib_gm: VanGravityModelResults = _gravity_model(
            te,
            name,
            gm_params,
            cost_matrix,
            calibrate,
            output_folder / f"gravity_model_{name}_calibration_log.csv",
        )
        # TODO put this back to normal once dev is done
        try:
            calibrate = gm_params.loc[name, "calibrate"]
            calib_gm = _gravity_model(
                te,
                name,
                input_paths,
                gm_params,
                calibrate,
                output_folder / f"gravity_model_{name}_calibration_log.csv",
            )

        # TODO handle dictionary outputs for run method
        except Exception as e:
            LOG.info("\t%s: %s", e.__class__.__name__, e)
            continue

        # Check if segment outputs a PA matrix which needs to be converted
        if name in PA_MATRICES:
            # Save PA matrix to CSV and convert to OD dataframe

            LOG.info("\tConverting PA to OD")

            pa_matrix = pd.DataFrame(calib_gm.distribution, index=te.index, columns=te.index)
            pa_matrix.to_csv(output_folder / (name + "-trip_matrix-PA.csv"))

            matrix = annual_pa_to_od(
                calib_gm.distribution.to_numpy(),
                te.loc[calib_gm.zones, "Attractions"].values,
                te.loc[calib_gm.zones, "Productions"].values,
            )

            matrices[name] = pd.DataFrame(
                matrix,
                index=calib_gm.zones,
                columns=calib_gm.zones,
            )
        else:
            matrices[name] = pd.DataFrame(
                calib_gm.distribution,
                index=calib_gm.zones,
                columns=calib_gm.zones,
            )

        # Save the annual matrix, TLD graph and Excel summary file
        matrices[name].to_csv(path_or_buf=output_folder / (name + "-trip_matrix-OD.csv"))

        with pd.ExcelWriter(output_folder / (name + "-GM_log.xlsx")) as writer:
            # TODO(kf) write out metadata

            summary = MatrixReport(
                matrices[name],
                pd.read_csv(input_paths.summary_zone_translation.path),
                f"{input_paths.summary_zone_translation.from_zoning}_id",
                f"{input_paths.summary_zone_translation.to_zoning}_id",
                f"{input_paths.summary_zone_translation.from_zoning}_to_{input_paths.summary_zone_translation.to_zoning}",
            )
            LOG.info("writing %s summary to excel", name)
            summary.write_to_excel(writer, output_matrix=True)

            for cat, gm_cat_results in calib_gm.info.items():
                if calibrate:
                    gm_cat_results.plot_distributions().savefig(
                        output_folder / (name + f"-distribution_{cat}.pdf")
                    )
                    gm_cat_results.cost_distribution.df.to_excel(
                        writer, sheet_name=f"Achieved Distribution {cat}", index=False
                    )

                    gm_cat_results.target_cost_distribution.df.to_excel(
                        writer, sheet_name=f"Target Distribution {cat}", index=False
                    )

            calib_gm.summary.to_excel(writer, sheet_name="Gravity Model Info")

            if name in PA_MATRICES:
                vehicle_kms = calculate_vehicle_kms(pa_matrix, cost_matrix)
                vehicle_kms.to_excel(writer, sheet_name="Vehicle Kilometres (PA)")

            vehicle_kms = calculate_vehicle_kms(matrices[name], cost_matrix)
            vehicle_kms.to_excel(writer, sheet_name="Vehicle Kilometres")
        LOG.info("\tFinished writing")

    return matrices


def matrix_time_periods(
    matrices: LGVMatrices, factors_path: Path, output_folder: Path
) -> dict[str, LGVMatrices]:
    """Converts all matrices to time periods based on factors in `factors_path`.

    Saves all matrices to sub-folder inside `output_folder`,
    the sub-folders have the same names as the time periods
    given.

    Parameters
    ----------
    matrices : LGVMatrices
        The trip matrices to be converted.
    factors_path : Path
        Path to Excel workbook containing time period
        factors.
    output_folder : Path
        Path to the folder where outputs are saved.

    Returns
    -------
    dict[str, LGVMatrices]
        Dictionary containing all matrices (values) for
        each time period (keys), contains the same time
        periods as given in the input table.

    See Also
    --------
    read_time_factors
        Function to read time period factors from `factors_path`.
    """
    factors = read_time_factors(factors_path)
    output_folder.mkdir(exist_ok=True)
    df = pd.DataFrame.from_dict(factors, orient="index")
    df.to_csv(output_folder / "time_period_factors.csv", index_label="Time Periods")
    tp_matrices = {}
    for tp, fac in factors.items():
        folder = output_folder / tp
        folder.mkdir(exist_ok=True)
        tmp_matrices = {}
        for name, mat in matrices.asdict().items():
            if name in ("zones", "combined"):
                continue
            mat = mat * fac.get(name)
            mat.to_csv(folder / f"{tp}_{name}-trip_matrix.csv")
            tmp_matrices[name] = mat
        tp_matrices[tp] = LGVMatrices(**tmp_matrices)
        tp_matrices[tp].combined.to_csv(folder / f"{tp}_combined-trip_matrix.csv")
    return tp_matrices


def produce_personal_matrix(
    folder: Path,
    purposes: list[int],
    year: int,
    normits_to_msoa_lookup: Path,
    factor: float,
    output_folder: Path,
) -> pd.DataFrame:
    """Produces LGV personal matrix by factoring NorMITs car other demand.

    Takes NoRMITS car other matrices for home based and non home bound,
    makes a dictionary of these values, concats them together, groups by origin,
    stacks the matrices to just 3 columns,
    then converts into NTEM zoning system using the lookup,
    finally a factor is applied to the output to account for just van personal trips.

    Parameters
    ----------
    folder : Path
        Location of car other matrices used for calculations.
    purposes : int
        Integer values defined in inputs which classifies the
        purpose.
    year : int
        Year of the model.
    normits_to_msoa_lookup: Path
        Path to normits to msoa(NTEM) lookup.
    factor: float
        Factor applied to end matrices so only van personal trips are contained.
    output_folder: Path
        Folder location where PA and OD matrices are saved

    Returns
    -------
    pd.DataFrame:
        Annual LGV personal trip matrices in NTEM zoning with
        3 columns: origin, destination, and values

    """
    # creating an empty dataframe
    matrix_list: list[pd.DataFrame] = []
    # reading in and appending home based daftaframes
    for purp in NTEM_PURPOSES["hb"]:
        if purp not in purposes:
            continue

        path = folder / f"hb_synthetic_pa_yr{int(year)}_p{purp}_m3.csv.bz2"
        df = pd.read_csv(path, index_col=0)
        df.columns = pd.to_numeric(df.columns, downcast="unsigned")
        # error check
        if not df.columns.equals(df.index):
            raise ValueError(f"index and columns aren't equal for '{path.name}'")
        matrix_list.append(df)

    # reading in and appending non home based data
    for purp in NTEM_PURPOSES["nhb"]:
        if purp not in purposes:
            continue

        for tp in PERSONAL_TIME_PERIODS:
            path = folder / f"nhb_synthetic_pa_yr{int(year)}_p{purp}_m3_tp{tp}.csv.bz2"
            df = pd.read_csv(path, index_col=0)
            df.columns = pd.to_numeric(df.columns, downcast="unsigned")
            # error check
            if not df.columns.equals(df.index):
                raise ValueError(f"index and columns aren't equal for '{path.name}'")
            matrix_list.append(df)

    # concatting all matrices from list
    matrix = pd.concat(matrix_list, axis=0).groupby(level=0).sum()
    # stacking matrices to long format and renaming columns
    matrix = matrix.stack().reset_index()
    matrix = matrix.rename(
        columns={"level_0": "origin", "level_1": "destination", 0: "values"}
    )

    # calling lookup
    # TODO Add column names to stop errors coming up
    lookup = Rezone.read(normits_to_msoa_lookup, None)
    # rezoning matrix NoHAM to NTEM
    matrix = Rezone.rezoneOD(
        matrix,
        lookup,
        dfCols=("origin", "destination"),
        rezoneCols="values",
    )

    # Apply personal LGV factor
    matrix["values"] = matrix["values"] * factor
    # Converting back to square matrices
    matrix = matrix.pivot(index="origin", columns="destination", values="values")

    # converting OD to PA matrices
    matrix.to_csv(output_folder / "personal-trip_matrix-PA.csv")
    od_matrix = annual_pa_to_od(
        matrix.values,
        matrix.sum(axis=0).values,
        matrix.sum(axis=1).values,
    )
    od_matrix = pd.DataFrame(od_matrix, index=matrix.index, columns=matrix.columns)
    od_matrix.to_csv(output_folder / "personal-trip_matrix-OD.csv")

    # TODO Add more tests at some point
    # negative and nans check
    negatives = (od_matrix < 0).values
    if np.any(negatives):
        raise ValueError(f"{np.sum(negatives)} negative values in matrix")
    nans = od_matrix.isna().values
    if np.any(nans):
        raise ValueError(f"{np.sum(nans)} nan values in matrix")
    return od_matrix


def produce_annual_matrices(
    input_paths: LGVInputPaths,
    trip_ends: LGVTripEnds,
    output_folder: Path,
    year: int,
) -> LGVMatrices:
    """Produces annual LGV matrices for all segments.

    The gravity model is an for all segments except personal,
    which is produced by aggregating and factoring NorMITs-Demand
    car matrices.

    Parameters
    ----------
    input_paths : LGVInputPaths
        Input paths config parameters.
    trip_ends : LGVTripEnds
        LGV trip ends to pass to the gravity model.
    output_folder : Path
        Folder to save outputs to.
    year : int
        Base year of the model.

    Returns
    -------
    LGVMatrices
        Annual LGV matrices.
    """
    LOG.info("Running gravity model to get annual matrices")
    matrices = run_gravity_model(
        input_paths,
        trip_ends,
        output_folder,
    )

    try:
        if input_paths.normits_pa_folder is None:
            personal_matrix = None
        else:
            LOG.info("Calculating personal segment matrices from NorMITs car demand")
            personal_matrix = produce_personal_matrix(
                input_paths.normits_pa_folder,
                input_paths.personal_purposes,
                year=year,
                normits_to_msoa_lookup=input_paths.normits_to_msoa_lookup,
                factor=input_paths.normits_to_personal_factor,
                output_folder=output_folder,
            )
            LOG.info("Finished personal segment matrices")

    except Exception as exc:
        personal_matrix = None
        warnings.warn(
            "Failed to produce personal matrix, this will not be included in the outputs."
            f" {exc.__class__.__name__}: {exc}",
            RuntimeWarning,
        )

    return LGVMatrices(**matrices, personal=personal_matrix)


def main(input_paths: LGVInputPaths):
    """Runs the LGV model.

    Parameters
    ----------
    input_paths : LGVInputPaths
        Paths to all the input files for the LGV model.
    """
    LOG.info("Getting model parameters")
    parameters = lgv_parameters(input_paths.parameters_path)
    LOG.debug("Model parameters:\n%s", pprint.pformat(parameters, indent=2, width=100))

    input_paths.save_yaml(input_paths.model_output_folder / "lgv_model_config.yml")

    LOG.info("Calculating trip ends")
    trip_ends = calculate_trip_ends(
        input_paths,
        input_paths.model_output_folder / "trip ends",
        parameters["lgv_growth"],
        parameters["year"],
    )

    LOG.info("Calculating annual matrices")
    annual_matrices = produce_annual_matrices(
        input_paths,
        trip_ends,
        input_paths.model_output_folder / "annual trip matrices",
        year=parameters["year"],
    )

    LOG.info("Calculating matrices by time period")
    matrix_time_periods(
        annual_matrices,
        input_paths.parameters_path,
        input_paths.model_output_folder / "time period matrices",
    )
    LOG.info("Done, it is now safe to close the tool")


def lgv_arg_parser() -> argparse.ArgumentParser:
    """Creates `ArgumentParser` for the LGV model.

    Returns
    -------
    argparse.ArgumentParser
        ArgumentParser which accepts the path to the
        config file, a flag to create an example file
        or nothing.
    """

    def file_path(path) -> Path:
        path = Path(path)
        if not path.is_file():
            raise ValueError("file doesn't exist")
        return path

    parser = argparse.ArgumentParser(prog=__package__, description=__doc__)
    parser.add_argument(
        "-c",
        "--config_file",
        type=file_path,
        help="Path to configuration file containing all LGV model inputs",
    )
    parser.add_argument(
        "-e",
        "--example",
        action="store_true",
        help="If given will write an example config " "file to the current working directory",
    )
    return parser


def _check_gm_inputs(
    trip_ends: pd.DataFrame, costs: pd.DataFrame, calibration: pd.DataFrame = None
) -> tuple[pd.DataFrame]:
    """Sorts the indices and checks the input DataFrames for `gravity_model`."""
    # Copy the DataFrames so links to them outside this function aren't edited
    data = [trip_ends.copy(), costs.copy()]
    names = ["trip_ends", "costs"]
    if calibration is not None:
        data.append(calibration.copy())
        names.append("calibration")
    for nm, df in zip(names, data):
        df.sort_index(axis=0, inplace=True)
        if df.index.has_duplicates:
            raise ValueError(f"duplicates not allowed in `{nm}` index")
        if df.columns.has_duplicates:
            raise ValueError(f"duplicates not allowed in `{nm}` columns")
        if nm == "trip_ends":
            continue
        df.sort_index(axis=1, inplace=True)
        if not (df.index.equals(data[0].index) and df.columns.equals(data[0].index)):
            raise ValueError(
                f"`{nm}` must be a square matrix with same zones as "
                "`trip_ends` for gravity model calculations"
            )
    # Raise error if costs contains zeros
    zero_costs = np.sum((costs == 0).values)
    if zero_costs > 0:
        raise ValueError(f"{zero_costs} zeros in cost matrix")
    return data


def calculate_vehicle_kms(
    matrix: pd.DataFrame, distances: pd.DataFrame, internals: Optional[set[int]] = None
) -> pd.DataFrame:
    """Summarise number of trips and vehicle kilometres by internal/external.

    Parameters
    ----------
    matrix : pd.DataFrame
        Square trip matrix, indices and columns should be
        zone numbers.
    distances : pd.DataFrame
        Square matrix of distances with the same indices
        and columns as `matrix`
    internals : set[int], optional
        Set of all internal zone numbers.

    Returns
    -------
    pd.DataFrame
        The number of trips and vehicle kilometres in the
        matrix, if `internals` is given then splits the totals
        into II, IE, EI and EE.
    """
    matrix, distances = _check_gm_inputs(matrix, distances)
    trips = {"All Trips": np.sum(matrix.values)}
    vehicle_kms = {"All Trips": np.sum((matrix * distances).values)}
    if internals:
        internals = set(internals)
        externals = list(set(matrix.index) - internals)
        internals = list(internals)

        filters = {
            "Internal-Internal": (internals, internals),
            "Internal-External": (internals, externals),
            "External-Internal": (externals, internals),
            "External-External": (externals, externals),
        }
        for nm, (index, cols) in filters.items():
            trips[nm] = np.sum(matrix.loc[index, cols].values)
            vehicle_kms[nm] = np.sum(
                (matrix.loc[index, cols] * distances.loc[index, cols]).values
            )
    df = pd.DataFrame(
        {("Trips", "Value"): trips, ("Vehicle Kilometers", "Value"): vehicle_kms}
    )
    if internals:
        for c in df.columns.get_level_values(0):
            df.loc[:, (c, "Percentage")] = df[(c, "Value")] / df.loc["All Trips", (c, "Value")]
        df.sort_index(axis=1, level=0, sort_remaining=False, inplace=True)
    return df


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
