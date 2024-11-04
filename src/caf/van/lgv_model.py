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
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

# Third Party
from caf.distribute import gravity_model, cost_functions

import caf.distribute.gravity_model
import caf.distribute.gravity_model.multi_area
from caf.toolkit import cost_utils
import numpy as np
import pandas as pd
import caf.distribute


# Local Imports
from caf.van.commute_segment import CommuteTripEnds
from caf.van.delivery_segment import DeliveryTripEnds
from caf.van.furnessing import annual_pa_to_od
from caf.van.gravity_model import CalibrateGravityModel, calculate_vehicle_kms
from caf.van.lgv_inputs import (
    GMInputs,
    LGVInputPaths,
    lgv_parameters,
    read_gm_params,
    read_study_area,
    read_time_factors,
)
from caf.van.rezone import Rezone
from caf.van.service_segment import ServiceTripEnds
from caf.van.utilities import DataPaths, read_csv, read_excel
from caf.van.matrix_validation import MatrixReport


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
PERSONAL_TIME_PERIODS = [1, 2, 3, 4]


TRIP_DISTRIBUTION_COLS = dict.fromkeys(
    ("start", "end", "average", "observed proportions"), float
)
"""Names and dtypes of the columns expected in the trip distributions input."""
FUNCTION_LABELS = {
    "log_normal": r"Log Normal: $\sigma={:.1e}$, $\mu={:.1e}$",
    "tanner": r"Tanner: $\alpha={:.1e}$, $\beta={:.1e}$",
}


"""Time periods to aggregate NHB together for."""

PA_DIFFERENCE_TOL = 1e-3

DUMMY_CAT = 1


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
    personal: pd.DataFrame
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
            "personal",
        )
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
    message_hook: Callable = print,
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
    message_hook : Callable, optional
        Function for writing messages, by default print

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

    bres_paths = DataPaths(
        "LGV BRES Data", input_paths.bres_path, input_paths.lsoa_lookup_path
    )

    model_zones: pd.Series = pd.read_csv(input_paths.model_study_area, usecols=["zone"])[
        "zone"
    ]
    model_zones.name = "Zone"

    LOG.info("Calculating Service trip ends")
    service = ServiceTripEnds(
        input_paths.household_paths,
        bres_paths,
        input_paths.parameters_path,
        lgv_growth,
        model_zones,
        input_paths.zoning
    )
    service.read()
    service.trip_ends.to_csv(output_folder / "service_trip_ends.csv")

    # Calculate the delivery trip ends and save outputs
    LOG.info("Calculating Delivery trip ends")
    delivery = DeliveryTripEnds(
        DataPaths(
            "LGV Delivery Warehouse", input_paths.warehouse_path, input_paths.lsoa_lookup_path
        ),
        bres_paths,
        input_paths.household_paths,
        input_paths.parameters_path,
        year,
        model_zones,
    )
    delivery.read()
    delivery.parcel_stem_trip_ends.to_csv(output_folder / "delivery_parcel_stem_trip_ends.csv")
    delivery.parcel_bush_trip_ends.to_csv(output_folder / "delivery_parcel_bush_trip_ends.csv")
    delivery.grocery_bush_trip_ends.to_csv(output_folder / "delivery_grocery_trip_ends.csv")

    # Calculate commuting trip ends and save output
    LOG.info("Calculating Commuting trip ends")
    commute = CommuteTripEnds(input_paths, model_zones)
    commute_trips = commute.trips
    for key in commute_trips:
        commute_trips[key].to_csv(output_folder / Path(f"commute_{key}_trip_ends.csv"))

    LOG.info("\tDone with trip ends")
    return LGVTripEnds(
        service=service.trip_ends,
        delivery_parcel_stem=delivery.parcel_stem_trip_ends,
        delivery_parcel_bush=delivery.parcel_bush_trip_ends,
        delivery_grocery=delivery.grocery_bush_trip_ends,
        commuting_drivers=commute_trips["Drivers"],
        commuting_skilled_trades=commute_trips["Skilled trades"],
    )


class VanGravityModelResults:
    distribution: pd.DataFrame
    summary: pd.DataFrame
    zones: np.ndarray
    info: dict[str | int, gravity_model.GravityModelResults]

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

    # check PA/OD are balanced - if not balance and add warning with difference
    if name in PA_MATRICES:
        trip_ends = balance_trip_ends(trip_ends, "Attractions", "Productions")
    else:
        trip_ends = balance_trip_ends(trip_ends, "Origins", "Destinations")

    tld_path = gm_data.trip_length_distribution_path

    # we have to do this because caf distribute does not look at index values, just order
    trip_ends = trip_ends.sort_index()  #
    # define zones to order everthing on

    if trip_ends.index.has_duplicates:
        raise KeyError("Trip ends have duplicated zones labels. Please fix this")

    zones = trip_ends.index.to_numpy()

    LOG.info("Running Gravity Model: %s, with calibration %s", name, calibrate)

    # nonzero returns a tuple with array of indices
    cost_matrix_validated = cost_matrix.loc[zones, zones].to_numpy()

    # different segments require different cost function and starting params - we determine extract these below

    tld = pd.read_csv(tld_path)

    # read in cat zone lookup if it exists 
    if gm_data.cat_zone_correspondance_path is not None:
        cat_zone_correspondence = pd.read_csv(gm_data.cat_zone_correspondance_path)
    else:
        #create a lookup for the whole matrix if cat zone hasnt been given
        cat_zone_correspondence = pd.DataFrame({"zone_id" : zones})
        cat_zone_correspondence["area"] = DUMMY_CAT
        tld["area"]= DUMMY_CAT


    if gm_data.cost_function == "log_normal":
        cost_function = cost_functions.BuiltInCostFunction.LOG_NORMAL.get_cost_function()
    elif gm_data.cost_function == "tanner":
        cost_function = cost_functions.BuiltInCostFunction.TANNER.get_cost_function()
    else:
        raise NotImplemented(
            f"cost function {gm_data.cost_function} is not implemented, please use either log_normal "
            "(mu, sigma) or tanner (alpha, beta)"
        )

    func_params = {}
    if isinstance(gm_data.cost_function_params, dict):
        # process params when they are a dict
        for cat, params in gm_data.cost_function_params.items():
            func_params[cat] = extract_cost_func_params(params, gm_data.cost_function)
    else:
        # process params when they are a tuple
        for cat in tld["area"].unique():
            func_params[cat] = extract_cost_func_params(
                gm_data.cost_function_params, gm_data.cost_function
            )

    cost_distributions = []

    # iterate through different TLD categories
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

    if name in PA_MATRICES:
        calib_gm = gravity_model.MultiAreaGravityModelCalibrator(
            trip_ends["Productions"].to_numpy(),
            trip_ends["Attractions"].to_numpy(),
            cost_matrix_validated,
            cost_function,
        )
    else:
        calib_gm = gravity_model.MultiAreaGravityModelCalibrator(
            trip_ends["Origins"].to_numpy(),
            trip_ends["Destinations"].to_numpy(),
            cost_matrix_validated,
            cost_function,
        )

    if calibrate:
        gravity_model_results = calib_gm.calibrate(
            cost_distributions,
            csv_logging_path,  # TODO figure out which key word args with default values needed to be changed
            caf.distribute.gravity_model.multi_area.GMCalibParams(),
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
    if cost_func_name == "log_normal":

        func_params = {  # TODO how do we set input Params
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


def balance_trip_ends(trip_ends: pd.DataFrame, target_col: str, test_col: str) -> pd.DataFrame:

    # determine difference in column totals
    trip_end_difference = trip_ends[target_col].sum() - trip_ends[test_col].sum()
    # avoid changing input out the function scope
    balanced_trip_ends = trip_ends.copy()

    if np.abs(trip_end_difference) > PA_DIFFERENCE_TOL:
        # calculate and apply factor to balance test col to target col
        factor = balanced_trip_ends[target_col].sum() / balanced_trip_ends[test_col].sum()

        LOG.warning(
            f"{target_col} and {test_col} are imbalanced (difference"
            f" = {trip_end_difference}) Factoring {test_col} to"
            f" {target_col} (factor = {factor})"
        )

        balanced_trip_ends[test_col] *= factor

    else:
        LOG.debug(
            f"Trip ends look fine \ntarget total {trip_ends[target_col].sum()}, \ntest total {trip_ends[test_col].sum()} \ndifference {trip_end_difference}"
        )

    return balanced_trip_ends


def run_gravity_model(
    input_paths: LGVInputPaths,
    trip_ends: LGVTripEnds,
    output_folder: Path,
    message_hook: Callable = print,
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
    message_hook : Callable, optional
        Function for writing messages, by default print

    Returns
    -------
    dict[str, pd.DataFrame]
        Trip matrices for each segment.
    """
    internals = read_study_area(input_paths.model_study_area)
    # gm_params = read_gm_params(input_paths.parameters_path)
    matrices: dict[str, pd.DataFrame] = {}
    output_folder.mkdir(exist_ok=True)

    cost_matrix = pd.read_csv(input_paths.cost_matrix_path, index_col=0)

    for name, te in trip_ends.asdict().items():
        if name == "zones":
            continue
        # TODO put this back to normal once dev is done
        # try:
        gm_params = input_paths.gm_parameters[name]
        calibrate = gm_params.calibrate
        calib_gm = _gravity_model(
            te,
            name,
            gm_params,
            cost_matrix,
            calibrate,
            output_folder / f"gravity_model_{name}_calibration_log.csv",
        )

        # TODO handle dictionary outputs for run method
        # except Exception as e:
        #    LOG.info("\t%s: %s", e.__class__.__name__, e)
        #    continue

        # Check if segment outputs a PA matrix which needs to be converted
        if name in PA_MATRICES:
            # Save PA matrix to CSV and convert to OD dataframe
            LOG.info("\tConverting PA to OD")
            # TODO KF: I am pretty sure this index and column labelling aligns, but I/you need to check
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
            # Calculate trip distributions for OD
        else:
            matrices[name] = pd.DataFrame(
                calib_gm.distribution,
                index=calib_gm.zones,
                columns=calib_gm.zones,
            )

        # Save the annual matrix, TLD graph and Excel summary file
        matrices[name].to_csv(path_or_buf=output_folder / (name + "-trip_matrix-OD.csv"))

        with pd.ExcelWriter(output_folder / (name + "-GM_log.xlsx")) as writer:
            # TODO write out metadata

            summary = MatrixReport(
                matrices[name],
                pd.read_csv(input_paths.ca_lookup_path),
                "NTEM_id",
                "CA_id",
                "NTEM_to_CA",
            )
            LOG.info(f"writing {name} summary to excel")
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
                vehicle_kms = calculate_vehicle_kms(pa_matrix, cost_matrix, internals)
                vehicle_kms.to_excel(writer, sheet_name="Vehicle Kilometres (PA)")

            vehicle_kms = calculate_vehicle_kms(matrices[name], cost_matrix, internals)
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
        personal_matrix = pd.DataFrame(
            np.ones_like(matrices["service"]),
            columns=matrices["service"].columns,
            index=matrices["service"].index,
        )
        warnings.warn(
            "Failed to produce personal matrix, use dummy matrix of 1s."
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
