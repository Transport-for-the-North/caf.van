import dataclasses
import logging
import pathlib
import warnings

import pandas as pd
import caf.toolkit as ctk
from caf.distribute import gravity_model, cost_functions, furness


from caf.van import lgv_inputs, lgv_model, utilities, __version__


# read in trip ends
# calculate trip end adjustment factors
# adjust trip ends
# 4d gravity model
# calculate trip distribution

LOG = logging.getLogger(__name__)

ANNUAL_MATRIX_DIR = "annual_matrices"


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
        return f"{ANNUAL_MATRIX_DIR}/{self.name}_prior_annual_od_matrix.csv"

    @property
    def annual_network_od_matrix_path(self) -> str:
        return f"{ANNUAL_MATRIX_DIR}/{self.name}_network_prior_annual_od_matrix.csv"

    @property
    def annual_sector_od_matrix_path(self) -> str:
        return f"{ANNUAL_MATRIX_DIR}/{self.name}_sector_prior_annual_od_matrix.csv"

    @property
    def annual_network_pa_matrix_path(self) -> str:
        return f"{ANNUAL_MATRIX_DIR}/{self.name}_network_prior_annual_pa_matrix.csv"

    @property
    def annual_sector_pa_matrix_path(self) -> str:
        return f"{ANNUAL_MATRIX_DIR}/{self.name}_sector_prior_annual_pa_matrix.csv"

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
        return pd.read_csv(output_path / self.annual_od_matrix_path, index_col=0)

    def get_network_annual_od_matrix(
        self, output_path: pathlib.Path, translation: pd.DataFrame
    ) -> pd.DataFrame:
        path = output_path / self.annual_network_od_matrix_path
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
                "to_network",
                "factors",
            )
            matrix.to_csv(path)
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
            return pd.read_csv(path, index_col=0)
        matrix = ctk.translation.pandas_matrix_zone_translation(
            self.get_annual_pa_matrix(), translation, "from", "to_network", "factors"
        )
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
    ):
        if self.pa_prior_matrices is not None:
            prior_matrix = self.get_annual_pa_matrix()
            sector_prior_matrix = self.get_sector_annual_pa_matrix(output_path, translations)
        else:
            prior_matrix = self.get_annual_od_matrix(output_path)

        adj_factors, sector_adj_factors = calculate_trip_end_adjustment_factors(
            prior_matrix, post_me_matrix, translations
        )
        sector_adj_factors.to_csv(
            output_path / f"{self.name}_sector_trip_end_adjustment_factors.csv"
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

        adj_trip_ends.to_csv(output_path / f"{self.name}_adjusted_trip_ends.csv", index=False)

        sector_target_matrix = ctk.translation.pandas_matrix_zone_translation(
            post_me_matrix, translations, "from", "to_sector", "factors"
        )

        balanced_adj_trip_ends = lgv_model.balance_trip_ends(
            adj_trip_ends.set_index("zone"),
            translations.rename(columns={"from": "zone_id", "to_sector": "area"}),
            "row_targets",
            "column_targets",
            self.name,
        )
        cost_matrix = pd.read_csv(cost_matrix_path, index_col=0)
        cost_matrix.columns = [int(col) for col in cost_matrix.columns]
        distribution = _4d_constraint_gravity_model(
            balanced_adj_trip_ends,
            self.name,
            self.gm_inputs,
            cost_matrix,
            translations,
            sector_target_matrix,
            calibrate=True,
            csv_logging_path=output_path / f"{self.name}_gravity_model.csv",
        )

        # Balance trip ends

        # 4d gravity model

        # calculate trip distribution

        pass


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
    row_post_totals = sector_prior_matrix.sum(axis=1)
    column_prior_totals = sector_post_matrix.sum(axis=0)
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
        (self.output_path / ANNUAL_MATRIX_DIR).mkdir(parents=True, exist_ok=True)

        self.create_annual_matrices(self.tp_annual_factors, self.output_path)

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

        for adjustment in self.adjustments:
            adjustment.run(
                self.post_me_purpose(prior_od_annual_matrix, translations, adjustment.name),
                translations,
                self.cost_matrix_path,
                self.output_path,
            )

    @property
    def annual_post_od_matrix_path(self) -> str:
        return f"{ANNUAL_MATRIX_DIR}/annual_post_od_matrix.csv"

    def get_annual_post_od_matrix(self) -> pd.DataFrame:
        return pd.read_csv(self.output_path / self.annual_post_od_matrix_path, index_col=0)

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

        od_to_pa_factors.to_csv(self.output_path / f"{name}_od_to_pa_factors.csv")

        return post_od_purposes * od_to_pa_factors

    @property
    def log_file(self):
        self.output_path.mkdir(parents=True, exist_ok=True)
        return self.output_path / "prior_adjustment.log"


def read_annual_matrix(
    paths: dict[str, pathlib.Path], tp_to_annual_factors: dict[str, pathlib.Path]
) -> pd.DataFrame:
    """Read in the annual matrix from the paths."""
    annual_matrix = None
    for tp, path in paths.items():
        if annual_matrix is None:
            annual_matrix = pd.read_csv(path, index_col=0) / tp_to_annual_factors[tp]
        else:
            annual_matrix += pd.read_csv(path, index_col=0) / tp_to_annual_factors[tp]
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
) -> lgv_model.VanGravityModelResults:
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

    sectoral_inputs = furness.SectoralConstraintInputs(
        constraint_area_trans,
        from_col="from",
        to_col="to_sector",
        factor_col="factors",
        target_mat=sector_target_matrix,
        zonal_zones=zones,
    )

    gravity_model_results = calib_gm.calibrate(
        cost_distributions,
        csv_logging_path,
        gravity_model.GMCalibParams(furness_jac=gm_data.furness_jacobian),
        return_distributions=False,
        four_d_inputs=sectoral_inputs,
        verbose=2,
    )

    results = lgv_model.VanGravityModelResults(
        calib_gm.achieved_distribution, zones, gravity_model_results
    )

    LOG.info("\tFinished, now writing outputs")
    return results


if __name__ == "__main__":

    config = PriorAdjustmentInput.load_yaml("prior_adjustment.yml")
    with ctk.LogHelper(
        "caf", ctk.ToolDetails(__package__, __version__), log_file=config.log_file
    ):
        config.run()
