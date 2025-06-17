# Built-Ins
import dataclasses
import logging
import pathlib
import warnings
from functools import reduce

# Third Party
import caf.toolkit as ctk
import pandas as pd
import tqdm.contrib.logging as tqdm_log
from caf.distribute import cost_functions, furness, gravity_model

# Local Imports
from caf.van import __version__, lgv_inputs, lgv_model, utilities

# read in trip ends
# calculate trip end adjustment factors
# adjust trip ends
# 4d gravity model
# calculate trip distribution

LOG = logging.getLogger(__name__)

INTERMEDIARY_MATRIX_DIR = "intermediary_matrices"
ANNUAL_MATRICES_DIR = "annual_matrices"


@dataclasses.dataclass
class PriorAdjustmentMatrix:
    name: str
    prior_trip_ends: pathlib.Path
    od_prior_matrices: dict[str, pathlib.Path]
    gm_inputs: utilities.GMInputs
    pa_prior_matrices: pathlib.Path | None = None

    def __post_init__(self):
        self._annual_od_matrix_path = None
        self._annual_od_matrix_path = None

    @property
    def annual_od_matrix_path(self) -> str:
        return f"{INTERMEDIARY_MATRIX_DIR}/{self.name}_prior_annual_od_matrix.csv"

    @property
    def annual_network_od_matrix_path(self) -> str:
        return f"{INTERMEDIARY_MATRIX_DIR}/{self.name}_network_prior_annual_od_matrix.csv"

    @property
    def annual_sector_od_matrix_path(self) -> str:
        return f"{INTERMEDIARY_MATRIX_DIR}/{self.name}_sector_prior_annual_od_matrix.csv"

    @property
    def annual_network_pa_matrix_path(self) -> str:
        return f"{INTERMEDIARY_MATRIX_DIR}/{self.name}_network_prior_annual_pa_matrix.csv"

    @property
    def annual_sector_pa_matrix_path(self) -> str:
        return f"{INTERMEDIARY_MATRIX_DIR}/{self.name}_sector_prior_annual_pa_matrix.csv"

    def write_annual_od_matrix(
        self, tp_to_annual_factors: dict[str, float], output_path: pathlib.Path
    ) -> None:
        path = output_path / self.annual_od_matrix_path
        if path.exists():
            warnings.warn(
                f"OD_matrix already exists at {path}."
                " Continuing with written file. If that is not desired, please delete the file."
            )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            LOG.info("Creating %s annual OD matrix at %s", self.name, path)
            read_annual_matrix(self.od_prior_matrices, tp_to_annual_factors).to_csv(path)

    def get_annual_od_matrix(self, output_path: pathlib.Path) -> pd.DataFrame:
        matrix = pd.read_csv(output_path / self.annual_od_matrix_path, index_col=0)
        matrix.columns = [int(col) for col in matrix.columns]
        return matrix

    def get_network_annual_od_matrix(
        self, output_path: pathlib.Path, translation: pd.DataFrame
    ) -> pd.DataFrame:
        path = output_path / self.annual_network_od_matrix_path
        if path.exists():
            warnings.warn(
                f"network OD matrix already exists at {path}."
                " Continuing with written file. If that is not desired, please delete the file."
            )
            matrix = pd.read_csv(path, index_col=0)
            matrix.columns = [int(col) for col in matrix.columns]
            return matrix

        matrix = ctk.translation.pandas_matrix_zone_translation(
            self.get_annual_od_matrix(output_path),
            translation,
            "from",
            "to_network",
            "factors",
        )
        matrix.to_csv(path)
        matrix.columns = [int(col) for col in matrix.columns]
        return matrix

    def get_sector_annual_od_matrix(
        self, output_path: pathlib.Path, translation: pd.DataFrame
    ) -> pd.DataFrame:
        path = output_path / self.annual_sector_od_matrix_path
        if path.exists():
            warnings.warn(
                f"network OD matrix already exists at {path}."
                " Continuing with written file. If that is not desired, please delete the file."
            )
            return pd.read_csv(path, index_col=0)
        else:
            matrix = ctk.translation.pandas_matrix_zone_translation(
                self.get_annual_od_matrix(output_path),
                translation,
                "from",
                "to_sector",
                "factors",
            )
            matrix.to_csv(path)
            return matrix

    def get_annual_pa_matrix(self) -> pd.DataFrame:
        if self.pa_prior_matrices is not None:
            return pd.read_csv(self.pa_prior_matrices, index_col=0)
        else:
            None

    def get_network_annual_pa_matrix(
        self, output_path: pathlib.Path, translation: pd.DataFrame
    ) -> pd.DataFrame:
        if self.pa_prior_matrices is None:
            return None
        path = output_path / self.annual_network_pa_matrix_path
        if path.exists():
            warnings.warn(
                f"network PA matrix already exists at {path}."
                " Continuing with written file. If that is not desired, please delete the file."
            )
            matrix = pd.read_csv(path, index_col=0)
            matrix.columns = [int(col) for col in matrix.columns]
            return matrix
        matrix = ctk.translation.pandas_matrix_zone_translation(
            self.get_annual_pa_matrix(), translation, "from", "to_network", "factors"
        )
        matrix.columns = [int(col) for col in matrix.columns]
        matrix.to_csv(path)

        return matrix

    def get_sector_annual_pa_matrix(
        self, output_path: pathlib.Path, translation: pd.DataFrame
    ) -> pd.DataFrame:
        if self.pa_prior_matrices is None:
            return None
        path = output_path / self.annual_sector_pa_matrix_path
        if path.exists():
            warnings.warn(
                f"network PA matrix already exists at {path}."
                " Continuing with written file. If that is not desired, please delete the file."
            )
            return pd.read_csv(path, index_col=0)
        matrix = ctk.translation.pandas_matrix_zone_translation(
            self.get_annual_pa_matrix(), translation, "from", "to_sector", "factors"
        )
        matrix.to_csv(path)
        return matrix

    def run(
        self,
        post_me_matrix: pd.DataFrame,
        translations: pd.DataFrame,
        cost_matrix_path: pd.DataFrame,
        output_path: pathlib.Path,
    ) -> pd.DataFrame:
        LOG.debug("adjusting tripends")
        if self.pa_prior_matrices is not None:
            prior_matrix = self.get_annual_pa_matrix()
        else:
            prior_matrix = self.get_annual_od_matrix(output_path)

        matrix_output_dir = output_path / ANNUAL_MATRICES_DIR
        matrix_output_dir.mkdir(parents=True, exist_ok=True)

        adj_factors, sector_adj_factors = calculate_trip_end_adjustment_factors(
            prior_matrix, post_me_matrix, translations
        )
        sector_adj_factors.to_csv(
            matrix_output_dir / f"{self.name}_sector_trip_end_adjustment_factors.csv"
        )
        del sector_adj_factors

        # read in trip ends
        trip_ends = pd.read_csv(self.prior_trip_ends)
        trip_ends = trip_ends.rename(
            columns={
                "Zone": "zone",
                "Productions": "row_targets",
                "Attractions": "column_targets",
                "Origins": "row_targets",
                "Destinations": "column_targets",
            }
        )

        adj_trip_ends = trip_ends.merge(
            adj_factors, how="outer", left_on="zone", right_on="demand"
        )
        adj_trip_ends["row_targets"] = (
            adj_trip_ends["row_targets"] * adj_trip_ends["row_factors"]
        )
        adj_trip_ends["column_targets"] = (
            adj_trip_ends["column_targets"] * adj_trip_ends["column_factors"]
        )

        adj_trip_ends = adj_trip_ends.drop(columns=["demand", "row_factors", "column_factors"])

        adj_trip_ends.to_csv(
            matrix_output_dir / f"{self.name}_adjusted_trip_ends.csv", index=False
        )

        LOG.info("Balancing trip ends")

        balanced_adj_trip_ends = lgv_model.balance_trip_ends(
            adj_trip_ends.set_index("zone"),
            translations.rename(columns={"from": "zone_id", "to_sector": "area"}),
            "row_targets",
            "column_targets",
            self.name,
        )
        LOG.info("running gravity model")
        sector_target_matrix = ctk.translation.pandas_matrix_zone_translation(
            post_me_matrix,
            create_network_to_sector_translation(translations),
            "network",
            "to_sector",
            "factors",
        )
        sector_target_matrix.to_csv(
            matrix_output_dir / f"{self.name}_sector_target_matrix.csv"
        )
        cost_matrix = pd.read_csv(cost_matrix_path, index_col=0)
        cost_matrix.columns = [int(col) for col in cost_matrix.columns]
        distribution, pre_constraint, sectoral_adj = _4d_constraint_gravity_model(
            balanced_adj_trip_ends,
            self.name,
            self.gm_inputs,
            cost_matrix,
            translations,
            sector_target_matrix,
            calibrate=True,
            csv_logging_path=matrix_output_dir / f"{self.name}_gravity_model.csv",
        )
        sectoral_adj.to_csv(matrix_output_dir / f"{self.name}_sectoral_adjustment_factors.csv")
        pre_constraint.to_csv(
            matrix_output_dir / f"{self.name}_pre_constraint_distribution.csv"
        )

        LOG.debug("Finished gravity model, processing results")

        od_annual_matrix = process_annual_matrices(
            distribution,
            True,
            balanced_adj_trip_ends,
            cost_matrix,
            matrix_output_dir,
            translations,
            self.name,
        )

        return od_annual_matrix


def create_network_to_sector_translation(translation: pd.DataFrame) -> pd.DataFrame:
    """Create network to sector translation."""
    # Create a translation matrix from the network to the sector
    network_to_sector = (
        translation.groupby(["to_network", "to_sector"])["factors"].first().reset_index()
    )
    network_to_sector = network_to_sector.rename(columns={"to_network": "network"})
    return network_to_sector


def calculate_trip_end_adjustment_factors(
    prior_matrix: pd.DataFrame, post_matrix: pd.DataFrame, translation: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate trip end adjustment factors."""
    # Calculate trip end adjustment factors
    network_to_sector = create_network_to_sector_translation(translation)
    sector_prior_matrix = ctk.translation.pandas_matrix_zone_translation(
        prior_matrix, translation, "from", "to_sector", "factors"
    )
    sector_post_matrix = ctk.translation.pandas_matrix_zone_translation(
        post_matrix, network_to_sector, "network", "to_sector", "factors"
    )

    row_prior_totals = sector_prior_matrix.sum(axis=1)
    row_post_totals = sector_post_matrix.sum(axis=1)
    column_prior_totals = sector_prior_matrix.sum(axis=0)
    column_post_totals = sector_post_matrix.sum(axis=0)

    # Calculate adjustment factors
    row_adjustment_factors = row_post_totals / row_prior_totals
    column_adjustment_factors = column_post_totals / column_prior_totals

    # Create a dataframe with the adjustment factors
    sector_adjustment_factors = pd.DataFrame(
        data={
            "row_factors": row_adjustment_factors,
            "column_factors": column_adjustment_factors,
        }
    )
    adjustment_factors = (
        translation.drop(columns="factors")
        .merge(sector_adjustment_factors, how="outer", left_on="to_sector", right_index=True)
        .rename(columns={"from": "demand"})
    )

    return (
        adjustment_factors[["demand", "row_factors", "column_factors"]].sort_values("demand"),
        sector_adjustment_factors,
    )


class PriorAdjustmentInput(ctk.BaseConfig):
    output_path: pathlib.Path
    post_me_matrix_path: dict[str, pathlib.Path]
    demand_to_network_path: ctk.translation.ZoneCorrespondencePath
    demand_to_sector_path: ctk.translation.ZoneCorrespondencePath
    tp_annual_factors: dict[str, float]
    cost_matrix_path: pathlib.Path
    adjustments: list[PriorAdjustmentMatrix]

    def run(self):
        self.output_path.mkdir(parents=True, exist_ok=True)
        (self.output_path / INTERMEDIARY_MATRIX_DIR).mkdir(parents=True, exist_ok=True)
        LOG.info("Creating annual matrices")
        self.create_annual_matrices(self.tp_annual_factors, self.output_path)
        LOG.info("Creating zone lookup")
        demand_to_network = self.demand_to_network_path.read(
            factors_mandatory=False, generic_column_names=True
        )
        demand_to_sector = self.demand_to_sector_path.read(
            factors_mandatory=False, generic_column_names=True
        )

        translations = demand_to_network.merge(
            demand_to_sector, how="outer", on="from", suffixes=("_network", "_sector")
        )
        # Translations are all aggregations, so we can set the factors to 1.
        # this is done so that it works with caf.toolkits translations functionality.
        translations["factors"] = 1

        prior_od_annual_matrix = self.prior_annual_totals(translations)

        LOG.info("Creating time period factors")
        tp_factors = sector_time_period_annual_factors(
            self.post_me_matrix_path,
            self.get_annual_post_od_matrix(),
            create_network_to_sector_translation(translations),
        )
        with pd.ExcelWriter(self.output_path / "time_period_factors.xlsx") as writer:
            for tp, factors in tp_factors.items():
                factors.to_excel(writer, sheet_name=tp)

        od_tp_matrices: dict[str, dict[str, pd.DataFrame]] = {}

        tp_matrix_dir = self.output_path / "TP_matrices"
        tp_matrix_dir.mkdir(parents=True, exist_ok=True)

        for adjustment in self.adjustments:
            LOG.info("Running adjustment %s", adjustment.name)
            od_annual_matrix = adjustment.run(
                self.post_me_purpose(prior_od_annual_matrix, translations, adjustment.name),
                translations,
                self.cost_matrix_path,
                self.output_path,
            )
            LOG.info("Finished adjustment %s, creating time period matrices", adjustment.name)
            for tp, factors in tp_factors.items():
                if od_tp_matrices.get(tp) is None:
                    od_tp_matrices[tp] = {}
                    (tp_matrix_dir / tp).mkdir(parents=True, exist_ok=True)
                zonal_factors = ctk.translation.pandas_matrix_zone_translation(
                    factors,
                    translations,
                    "to_sector",
                    "from",
                    "factors",
                )
                od_tp_matrices[tp][adjustment.name] = od_annual_matrix * zonal_factors
                od_tp_matrices[tp][adjustment.name].to_csv(
                    tp_matrix_dir / tp / f"{adjustment.name}_annual_od_matrix_{tp}.csv"
                )
        LOG.info(
            "Finished creating time period matrices, creating combined matrix and convertinmg to noham"
        )
        for tp, od_matrices in od_tp_matrices.items():
            tp_sum = reduce(lambda x, y: x.add(y, fill_value=0), od_matrices.values())
            tp_sum.to_csv(tp_matrix_dir / f"{tp}_normits_od_matrix.csv")
            ctk.translation.pandas_matrix_zone_translation(
                tp_sum, translations, "from", "to_network", "factors"
            ).to_csv(tp_matrix_dir / f"{tp}_noham_od_matrix.csv")

    @property
    def annual_post_od_matrix_path(self) -> str:
        return f"{INTERMEDIARY_MATRIX_DIR}/annual_post_od_matrix.csv"

    def get_annual_post_od_matrix(self) -> pd.DataFrame:
        matrix = pd.read_csv(self.output_path / self.annual_post_od_matrix_path, index_col=0)
        matrix.columns = [int(col) for col in matrix.columns]
        return matrix

    def create_annual_matrices(
        self, tp_to_annual_factors: dict[str, float], output_path: pathlib.Path
    ) -> None:
        for adjustment in self.adjustments:
            adjustment.write_annual_od_matrix(tp_to_annual_factors, output_path)

        post_me_path = output_path / self.annual_post_od_matrix_path
        read_annual_matrix(self.post_me_matrix_path, tp_to_annual_factors).to_csv(post_me_path)

    def prior_annual_totals(self, translation: pd.DataFrame) -> pd.DataFrame:
        prior_od_annual_matrix: pd.DataFrame | None = None
        for adjustment in self.adjustments:
            if prior_od_annual_matrix is None:
                prior_od_annual_matrix = adjustment.get_network_annual_od_matrix(
                    self.output_path, translation
                )
            else:
                prior_od_annual_matrix += adjustment.get_network_annual_od_matrix(
                    self.output_path, translation
                )
        assert prior_od_annual_matrix is not None, "No prior OD matrices found"
        return prior_od_annual_matrix

    def post_me_purpose(
        self, prior_od_annual_matrix: pd.DataFrame, translation: pd.DataFrame, name: str
    ) -> pd.DataFrame:
        selected_adjustment: PriorAdjustmentMatrix | None = None
        for adjustment in self.adjustments:
            if adjustment.name == name:
                selected_adjustment = adjustment
                # read in the pa matrix
        assert selected_adjustment is not None, f"No adjustment found for {name}"

        purpose_factors = (
            selected_adjustment.get_network_annual_od_matrix(self.output_path, translation)
            / prior_od_annual_matrix
        )

        post_od_purposes = self.get_annual_post_od_matrix() * purpose_factors

        if selected_adjustment.pa_prior_matrices is None:

            return post_od_purposes

        od_to_pa_factors = selected_adjustment.get_network_annual_pa_matrix(
            self.output_path, translation
        ) / selected_adjustment.get_network_annual_od_matrix(self.output_path, translation)
        # TODO fillna with 0 or 1?
        od_to_pa_factors = od_to_pa_factors.fillna(0)
        od_to_pa_factors.to_csv(self.output_path / f"{name}_od_to_pa_factors.csv")

        return post_od_purposes * od_to_pa_factors

    @property
    def log_file(self):
        self.output_path.mkdir(parents=True, exist_ok=True)
        return self.output_path / "prior_adjustment.log"


def sector_time_period_annual_factors(
    tp_matrices: dict[str, pathlib.Path],
    annual_matrix: pd.DataFrame,
    translation: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    annual_gor_matrix = ctk.translation.pandas_matrix_zone_translation(
        annual_matrix, translation, "network", "to_sector", "factors"
    )
    for tp, path in tp_matrices.items():
        sector_tp_matrix = ctk.translation.pandas_matrix_zone_translation(
            pd.read_csv(path, index_col=0), translation, "network", "to_sector", "factors"
        )
        tp_matrices[tp] = sector_tp_matrix / annual_gor_matrix

    return tp_matrices


def read_annual_matrix(
    paths: dict[str, pathlib.Path], tp_to_annual_factors: dict[str, pathlib.Path]
) -> pd.DataFrame:
    factor = {"AM": 0.125, "IP": 0.25, "PM": 0.125, "OP": 0.5}
    """Read in the annual matrix from the paths."""
    annual_matrix = None
    for tp, path in paths.items():
        if annual_matrix is None:
            annual_matrix = (pd.read_csv(path, index_col=0) / tp_to_annual_factors[tp]) * factor[tp]
        else:
            annual_matrix += (pd.read_csv(path, index_col=0) / tp_to_annual_factors[tp]) * factor[tp]

    return annual_matrix


def _4d_constraint_gravity_model(
    trip_ends: pd.DataFrame,
    name: str,
    gm_data: utilities.GMInputs,
    cost_matrix: pd.DataFrame,
    constraint_area_trans: pd.DataFrame,
    sector_target_matrix: pd.DataFrame,
    calibrate: bool,
    csv_logging_path: pathlib.Path,
) -> tuple[lgv_model.VanGravityModelResults, pd.DataFrame, pd.DataFrame]:
    """Internal function used in `run_gravity_model` for running the GM with calibration."""

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
        cat_zone_correspondence["area"] = lgv_model.DUMMY_CAT
        tld["area"] = lgv_model.DUMMY_CAT

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
            func_params[cat] = lgv_model.extract_cost_func_params(
                params, gm_data.cost_function
            )
    else:
        # process params when they are a tuple
        for cat in tld["area"].unique():
            func_params[cat] = lgv_model.extract_cost_func_params(
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
        trip_ends["column_targets"].to_numpy(),
        cost_matrix_validated,
        cost_function,
    )

    gravity_model_results = calib_gm.calibrate(
        cost_distributions,
        csv_logging_path,
        gravity_model.GMCalibParams(furness_jac=gm_data.furness_jacobian),
        return_distributions=False,
        verbose=2,
    )
   

    sectoral_inputs = furness.SectoralConstraintInputs(
        constraint_area_trans,
        from_col="from",
        to_col="to_sector",
        factor_col="factors",
        target_mat=sector_target_matrix,
        zonal_zones=zones,
        # furness_inputs=furness.FurnessInputs(
        #    seed_vals= calib_gm.achieved_distribution,
        #    row_targets=trip_ends["row_targets"].to_numpy(),
        #    column_targets=trip_ends["column_targets"].to_numpy(),
    )

    matrix, sectoral_factors = furness.sectoral_constraint(
        pd.DataFrame(calib_gm.achieved_distribution, index=zones, columns=zones),
        sectoral_inputs,
        furness_inputs=furness.FurnessInputs(
        seed_vals= calib_gm.achieved_distribution,#TODO THIS VERY VERY BAD. THIS IS NOT THE SEED VAL USED BUT NEED IT TO INITIALISE CLASS, FIX THIS
        row_targets=trip_ends["row_targets"].to_numpy(),
        col_targets=trip_ends["column_targets"].to_numpy(),)
    )

    results = lgv_model.VanGravityModelResults(matrix, zones, gravity_model_results)

    return results, pd.DataFrame(calib_gm.achieved_distribution, index=zones, columns=zones), sectoral_factors


def process_annual_matrices(
    calib_results: lgv_model.VanGravityModelResults,
    is_pa_matrix: bool,
    trip_ends: pd.DataFrame,
    cost_matrix: pd.DataFrame,
    output_folder: pathlib.Path,
    sector_translation: pd.DataFrame,
    name: str,
) -> pd.DataFrame:
    if is_pa_matrix:
        # Save PA matrix to CSV and convert to OD dataframe

        LOG.info("\tConverting PA to OD")

        pa_matrix = pd.DataFrame(
            calib_results.distribution, index=trip_ends.index, columns=trip_ends.index
        )
        pa_matrix.to_csv(output_folder / (name + "-trip_matrix-PA.csv"))

        matrix = lgv_model.annual_pa_to_od(
            calib_results.distribution.to_numpy(),
            trip_ends.loc[calib_results.zones, "column_targets"].values,
            trip_ends.loc[calib_results.zones, "row_targets"].values,
        )

        matrix = pd.DataFrame(
            matrix,
            index=calib_results.zones,
            columns=calib_results.zones,
        )
    else:
        matrix = pd.DataFrame(
            calib_results.distribution,
            index=calib_results.zones,
            columns=calib_results.zones,
        )

    # Save the annual matrix, TLD graph and Excel summary file
    matrix.to_csv(path_or_buf=output_folder / (name + "-trip_matrix-OD.csv"))

    with pd.ExcelWriter(output_folder / (name + "-GM_log.xlsx")) as writer:
        # TODO(kf) write out metadata

        summary = ctk.pandas_utils.MatrixReport(
            matrix,
            translation_factors=sector_translation,
            translation_from_col="from",
            translation_to_col="to_sector",
            translation_factors_col="factors",
        )
        LOG.info("writing %s summary to excel", name)
        summary.write_to_excel(writer, output_sector_matrix=True)

        for cat, gm_cat_results in calib_results.info.items():

            gm_cat_results.plot_distributions().savefig(
                output_folder / (name + f"-distribution_{cat}.pdf")
            )
            gm_cat_results.cost_distribution.df.to_excel(
                writer, sheet_name=f"Achieved Distribution {cat}", index=False
            )

            gm_cat_results.target_cost_distribution.df.to_excel(
                writer, sheet_name=f"Target Distribution {cat}", index=False
            )

        calib_results.summary.to_excel(writer, sheet_name="Gravity Model Info")

        if is_pa_matrix:
            vehicle_kms = lgv_model.calculate_vehicle_kms(pa_matrix, cost_matrix)
            vehicle_kms.to_excel(writer, sheet_name="Vehicle Kilometres (PA)")

        vehicle_kms = lgv_model.calculate_vehicle_kms(matrix, cost_matrix)
        vehicle_kms.to_excel(writer, sheet_name="Vehicle Kilometres")
    LOG.info("\tFinished writing")
    return matrix


if __name__ == "__main__":

    config = PriorAdjustmentInput.load_yaml("prior_adjustment.yml")
    with ctk.LogHelper(
        "caf", ctk.ToolDetails(__package__, __version__), log_file=config.log_file
    ) as log:
        # accessing protected attribute is bad, but we have to so we can set the logging level
        tqdm_log.logging_redirect_tqdm(
            [log.logger, log._warning_logger]  # pylint: disable="protected-access"
        )

        log.add_console_handler(log_level=logging.DEBUG)
        config.run()
