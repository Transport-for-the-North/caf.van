# -*- coding: utf-8 -*-
"""
Script for growing the LGV model inputs to a forecast year.

This is only necessary for inputs which aren't already
available for forecast years.
"""

##### IMPORTS #####

# Built-Ins
import datetime as dt
import logging
import pathlib
import sys
from typing import Any, Callable, Iterator

# Third Party
import caf.toolkit
import numpy as np
import pandas as pd
import pydantic
import strictyaml
from matplotlib import pyplot as plt
from matplotlib import ticker
from pydantic import dataclasses, types
from scipy import stats

sys.path.extend(["src"])
# Local Imports
# pylint: disable=wrong-import-position
import caf.van
from caf.van import commute_segment, lgv_inputs, utilities

# pylint: enable=wrong-import-position

##### CONSTANTS #####
LOG = logging.getLogger("caf.van.lgv_forecast_inputs")
CONFIG_PATH = pathlib.Path("src/scripts/lgv_forecast_inputs.yml")
BASE_LGV_GROWTH_FACTOR = 1.51
LGV_SURVEY_YEAR = 2003
CSV_COMMENT_CHARACTER = "#"


##### CLASSES #####
class ForecastInputsConfig(caf.toolkit.BaseConfig):
    base_model_config: types.FilePath
    base_year: int
    forecast_year: int
    output_folder: types.DirectoryPath
    oa_lookup_path: types.FilePath
    base_planning_path: types.FilePath
    forecast_planning_path: types.FilePath
    forecasted_vehicle_kms: types.FilePath
    fleet_growth: types.FilePath


@dataclasses.dataclass(config={"arbitrary_types_allowed": True})
class NTEMGrowthData:
    lsoa: pd.DataFrame
    msoa: pd.DataFrame
    lad: pd.DataFrame

    pop_col: str = "population"
    households_col: str = "households"
    jobs_col: str = "jobs"
    workers_col: str = "workers"

    @pydantic.root_validator(skip_on_failure=True)
    def _check_columns(cls, values: dict[str, Any]) -> dict[str, Any]:
        # pylint: disable=no-self-argument
        col_names = ["pop_col", "households_col", "jobs_col", "workers_col"]
        columns = [values[i] for i in col_names]

        for name in ("lsoa", "msoa", "lad"):
            data: pd.DataFrame = values[name]

            missing = [i for i in columns if i not in data.columns]
            if len(missing) > 0:
                raise ValueError(f"{len(missing)} columns missing from {name}: {missing}")

            values[name] = data[columns]

        return values

    def __iter__(self) -> Iterator[tuple[str, pd.DataFrame]]:
        yield "lsoa", self.lsoa
        yield "msoa", self.msoa
        yield "lad", self.lad


class _GrowthFactorLinRegress:
    # TODO Add docstrings to class and methods
    def __init__(self, data: pd.Series) -> None:
        self._data = data
        self._results = stats.linregress(data.index, data.values)

    @property
    def name(self) -> str:
        return self._data.name

    def line(self, x: np.ndarray) -> np.ndarray:
        return (self._results.slope * x) + self._results.intercept

    def year_value(self, x: int):
        if x in self._data.index:
            return self._data.at[x]
        else:
            return self.line(x)

    @property
    def data(self) -> pd.Series:
        return self._data.copy()

    @property
    def slope(self) -> float:
        return self._results.slope

    @property
    def intercept(self) -> float:
        return self._results.intercept

    @property
    def rvalue(self) -> float:
        return self._results.rvalue


##### FUNCTIONS #####
def _load_planning_data(base_path: pathlib.Path, forecast_path: pathlib.Path):
    """Calculate growth values for the TEMPro planning data for the forecast year."""
    # TODO(MB) Load NTEM data directly from the databases, functionality for this
    # exists in NorMITs-Demand
    index_col = ["Area Description", "Name"]
    rename_columns = {
        "Total": NTEMGrowthData.pop_col,
        "HHs": NTEMGrowthData.households_col,
        "Jobs": NTEMGrowthData.jobs_col,
        "Workers": NTEMGrowthData.workers_col,
    }
    columns = {**dict.fromkeys(index_col, str), **dict.fromkeys(rename_columns.keys(), float)}

    dataframes = []
    for name, path in (("base", base_path), ("forecast", forecast_path)):
        data = utilities.read_csv(
            path, f"{name} Household projections", columns=columns, index_col=index_col
        )
        data = data.rename(columns=rename_columns)
        data.columns = pd.MultiIndex.from_product([[name], data.columns.str.lower()])
        dataframes.append(data)

    return pd.concat(dataframes, axis=1)


def load_oa_lookup(path: pathlib.Path) -> pd.DataFrame:
    # TODO Docstring
    columns = ["lsoa11cd", "msoa11cd", "ladcd", "ladnm"]
    LOG.info("Reading OA lookup: %s", path.name)
    lookup = pd.read_csv(path, usecols=columns, dtype=str)
    lookup = lookup.rename(columns={"lsoa11cd": "lsoa", "msoa11cd": "msoa", "ladcd": "lad"})
    return lookup.drop_duplicates()


def _normalise_names(data: pd.Series) -> pd.Series:
    # TODO Docstring
    data = data.str.lower().str.strip()
    data = data.str.replace(r"[!\"#$%&'\()*+,-./:;<=>?@\][\\^_`{|}~]", "", regex=True)
    data = data.str.replace(r"\s+", " ", regex=True)

    return data


def _normalise_lad_names(data: pd.Series) -> pd.Series:
    # TODO Docstring
    data = _normalise_names(data)

    lad_renaming = {
        "the vale of glamorgan": "vale of glamorgan",
        "comhairle nan eilean siar": "na heileanan siar",
        "shepway": "folkestone and hythe",
    }

    return data.replace(lad_renaming)


def _merge_check(
    data: pd.DataFrame, title: str, merge_data: str, left_name: str, right_name: str
) -> None:
    # TODO Docstring
    source_lookup = {"left_only": left_name, "right_only": right_name, "both": "both"}

    total = len(data)
    uniques = np.unique(data["_merge"], return_counts=True)

    for loc, n in zip(*uniques):
        if loc == "both":
            dataset = "both datasets"
        else:
            dataset = f"{source_lookup[loc]} dataset only"

        LOG.warning(
            "%s (%s) %s found in %s, for %s",
            n,
            f"{n / total:.0%}",
            merge_data,
            dataset,
            title,
        )


def get_planning_growth(
    base_path: pathlib.Path, forecast_path: pathlib.Path, lookup: pd.DataFrame
) -> NTEMGrowthData:
    # TODO Docstring
    planning_data = _load_planning_data(base_path, forecast_path)

    lad_growth: pd.DataFrame = planning_data.loc["Authority"]
    lad_growth = lad_growth["forecast"] / lad_growth["base"]
    lad_lookup = lookup.groupby(["lad", "ladnm"], as_index=False)[["lad", "ladnm"]].first()
    lad_lookup.loc[:, "ladnm"] = _normalise_lad_names(lad_lookup["ladnm"])

    lad_growth.index = _normalise_lad_names(lad_growth.index.to_series())
    lad_growth = lad_growth.merge(
        lad_lookup,
        left_index=True,
        right_on="ladnm",
        validate="1:1",
        how="outer",
        indicator=True,
    )

    _merge_check(
        lad_growth,
        "LAD growth factors",
        "LAD names",
        left_name="planning data",
        right_name="LAD lookup",
    )
    lad_growth = (
        lad_growth.set_index("lad").drop(columns=["ladnm", "_merge"]).dropna(how="any")
    )

    planning_data.index = planning_data.index.droplevel("Name")
    msoa_mask = planning_data.index.str.match(r"[ESWN]\d+", case=False)
    msoa_growth: pd.DataFrame = (
        planning_data.loc[msoa_mask, "forecast"] / planning_data.loc[msoa_mask, "base"]
    )

    lsoa_lookup = lookup.groupby(["msoa", "lsoa"], as_index=False)[["msoa", "lsoa"]].first()
    msoa_growth = msoa_growth.merge(
        lsoa_lookup,
        left_index=True,
        right_on="msoa",
        how="outer",
        validate="1:m",
        indicator=True,
    )

    _merge_check(msoa_growth, "LSOA growth factors", "MSOAs", "planning data", "LSOA lookup")
    msoa_growth = msoa_growth.drop(columns="_merge")

    lsoa_growth = msoa_growth.drop(columns="msoa").groupby("lsoa").first().dropna(how="any")
    msoa_growth = msoa_growth.drop(columns="lsoa").groupby("msoa").first().dropna(how="any")

    return NTEMGrowthData(lsoa=lsoa_growth, msoa=msoa_growth, lad=lad_growth)


def grow_occupation_data(
    ew_path: pathlib.Path,
    sc_path: pathlib.Path,
    growth: NTEMGrowthData,
    base_year: int,
    forecast_year: int,
    output_folder: pathlib.Path,
) -> tuple[dict[str, pathlib.Path], dict[str, pd.DataFrame]]:
    """Grow occupation data to forecast year."""

    def filter_float(data: dict[str, type]) -> list[str]:
        return [k for k, v in data.items() if v is float]

    factor_col = growth.workers_col

    meta_rows = {}
    for key, path in (("EW", ew_path), ("SC", sc_path)):
        meta_rows[key] = ""

        with open(path, "rt", encoding="utf-8") as file:
            for _ in range(commute_segment.QS606_HEADER_FOOTER[key][0]):
                line = file.readline()
                if "Date" in line:
                    line = line[: line.rfind('"')] + f' grown to {forecast_year}"\n'

                meta_rows[key] += line

    base_data = commute_segment.read_qs606(ew_path, sc_path, False)

    qs_data = {}
    # Use LSOA growth factors for England & Wales
    qs_data["EW"] = base_data["EW"].merge(
        growth.lsoa[factor_col],
        how="left",
        left_on=list(commute_segment.QS606_BASE_HEADERS.keys())[0],
        right_index=True,
        validate="1:1",
        indicator=True,
    )
    _merge_check(
        qs_data["EW"], "England & Wales occupation", "LSOAs", "base occupation", "LSOA growth"
    )

    data_columns: dict[str, list[str]] = {
        k: filter_float(v) for k, v in commute_segment.QS606_HEADERS.items()
    }
    key = "EW"
    for column in data_columns[key]:
        qs_data[key].loc[:, column] = qs_data[key][column] * qs_data[key][factor_col]
    LOG.info(
        "Growing England & Wales occupation from %s to %s using LSOA %s",
        base_year,
        forecast_year,
        factor_col,
    )

    # TODO Use more spatially disaggregate values for Scotland
    # Use single average growth factor for Scotland because they're datazones not LSOAs
    key = "SC"
    qs_data[key] = base_data[key]
    scot_growth_mask = growth.lad.index.str.lower().str.startswith("s")
    avg_growth = growth.lad.loc[scot_growth_mask, factor_col].mean()
    for column in data_columns[key]:
        qs_data[key].loc[:, column] = qs_data[key][column] * avg_growth
    LOG.info(
        "Growing Scotland occupation from %s to %s using average Scottish growth "
        "(%s) because Scotland data is given by datazone instead of LSOA",
        base_year,
        forecast_year,
        factor_col,
    )

    output_paths: dict[str, pathlib.Path] = {}
    comparisons = {}
    for key, data in qs_data.items():
        output_paths[key] = output_folder / f"QS606{key}_grown_{forecast_year}.csv"
        data = data.drop(columns=[factor_col, "_merge"], errors="ignore")

        comparisons[key] = compare_column_totals(base_data[key], data)

        with open(output_paths[key], "wt", encoding="utf-8", newline="") as file:
            file.write(meta_rows[key])
            data.to_csv(file, index=False)

        LOG.info("Written grown occupation data to: %s", output_paths[key].name)

    return output_paths, comparisons


def grow_warehouse_data(
    base_path: pathlib.Path,
    commute_paths: lgv_inputs.CommuteWarehousePaths,
    growth: NTEMGrowthData,
    base_year: int,
    forecast_year: int,
    output_folder: pathlib.Path,
) -> tuple[dict[str, pathlib.Path], dict[str, pd.DataFrame]]:
    """Grow warehouse data to forecast year."""
    factor_col = growth.jobs_col
    zone_col = "LSOA11CD"
    data_col = "area"

    paths = [
        ("delivery", base_path),
        ("commute_high", commute_paths.high),
        ("commute_medium", commute_paths.medium),
        ("commute_low", commute_paths.low),
    ]
    output_paths: dict[str, pathlib.Path] = {}
    comparisons: dict[str, pd.DataFrame] = {}

    for name, path in paths:
        base_data = utilities.read_csv(path, columns={zone_col: str, data_col: float})

        data = base_data.merge(
            growth.lsoa[factor_col],
            how="left",
            left_on=zone_col,
            right_index=True,
            validate="1:1",
            indicator=True,
        )
        _merge_check(
            data, f"growing {name} warehouse", "LSOAs", f"{name} warehouse", "LSOA growth"
        )
        data.loc[:, data_col] = data[data_col] * data[factor_col]
        data = data.drop(columns=[factor_col, "_merge"])

        comparisons[name] = compare_column_totals(base_data, data)

        output_paths[name] = output_folder / f"{name}_grown_{forecast_year}.csv"
        data.to_csv(output_paths[name], index=False)
        LOG.info(
            "Grown %s from %s to %s with %s, written to %s",
            name,
            base_year,
            forecast_year,
            factor_col,
            output_paths[name].name,
        )

    return output_paths, comparisons


def _recursive_apply(data: dict[str, Any], func: Callable) -> dict[str, Any]:
    # TODO Docstring
    for key, value in data.items():
        if isinstance(value, dict):
            data[key] = _recursive_apply(value, func)
        elif isinstance(value, (list, tuple)):
            data[key] = [func(i) for i in value]
        else:
            data[key] = func(value)

    return data


def write_forecast_log(
    paths: dict[str, Any],
    output_path: pathlib.Path,
    base_year: int,
    forecast_year: int,
) -> None:
    # TODO Docstring
    yaml = strictyaml.as_document(_recursive_apply(paths, str)).as_yaml()

    with open(output_path, "wt", encoding="utf-8") as file:
        file.write(
            f"# LGV model inputs grown from {base_year} to {forecast_year}, "
            f"produced at: {dt.datetime.now():%c}\n"
        )
        file.write(yaml)

    LOG.info("Written output log to %s", output_path)


def _plot_linear_fit(
    fit: _GrowthFactorLinRegress, base_year: int, forecast_year: int, output_path: pathlib.Path
) -> None:
    # TODO Docstring
    fig, ax = plt.subplots(figsize=(10, 10))
    fig.set_tight_layout(True)
    ax.set_ylabel(fit.name)
    ax.set_xlabel("Year")
    ax.set_title(
        f"Linear Regression of {fit.name}\nto Recalculate Growth Factors", fontsize="x-large"
    )

    ax.scatter(fit.data.index, fit.data.values, label="RTF Data", c="C0")
    ax.plot(
        fit.data.index,
        fit.line(fit.data.index),
        c="C1",
        ls="--",
        label=f"Linear Fit: $y={fit.slope:.2f}x"
        f"{+fit.intercept:.0f}$, $R^2={fit.rvalue**2:.2f}$",
    )

    years = {"LGV Survey": LGV_SURVEY_YEAR, "Base": base_year, "Forecast": forecast_year}
    for nm, yr in years.items():
        val = fit.year_value(yr)
        ax.annotate(
            f"{nm} Year\n({yr})",
            (yr, val),
            arrowprops=dict(arrowstyle="->", color="C2"),
            xytext=(yr + 2, val * 0.9),
            bbox=dict(fc=(0.8, 1, 0.8, 0.5), alpha=0.5, ec="C2", boxstyle="Round"),
        )

    ax.set_ylim(0, None)
    ax.set_xlim(min(LGV_SURVEY_YEAR, base_year, forecast_year, fit.data.index.min()) - 1, None)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid()
    ax.grid(which="minor", ls=":")
    plt.legend()

    fig.savefig(output_path)
    plt.close()
    LOG.info("Written: %s", output_path.name)


def _calculate_growth_factors(
    fit: _GrowthFactorLinRegress, base_year: int, forecast_year: int, plot_path: pathlib.Path
) -> dict[str, float]:
    _plot_linear_fit(fit, base_year, forecast_year, plot_path)

    base_projection = fit.year_value(base_year)
    survey_projection = fit.year_value(LGV_SURVEY_YEAR)
    forecast_projection = fit.year_value(forecast_year)

    base_growth = base_projection / survey_projection
    forecast_growth = forecast_projection / survey_projection
    growth_adjust = BASE_LGV_GROWTH_FACTOR / base_growth

    return {
        "Survey year": LGV_SURVEY_YEAR,
        "Base year": base_year,
        "Forecast year": forecast_year,
        "Projection growth to base": base_growth,
        "Projection growth to forecast": forecast_growth,
        "Base growth factor": BASE_LGV_GROWTH_FACTOR,
        "Growth adjustment factor": growth_adjust,
        "Growth factor survey to forecast": growth_adjust * forecast_growth,
        "Growth factor base to forecast": fit.year_value(forecast_year)
        / fit.year_value(base_year),
    }


def calculate_veh_km_growth_factor(
    veh_kms_path: pathlib.Path, base_year: int, forecast_year: int, plot_path: pathlib.Path
) -> dict[str, float]:
    # TODO Docstring
    rtf_veh_kms = pd.read_excel(
        veh_kms_path,
        sheet_name="Table 1 - Traffic - Area Type",
        skiprows=3,
        usecols=range(1, 12),
        nrows=30,
    )
    index_cols = ["Region", "Area type", "Vehicle Type"]
    rtf_veh_kms.loc[:, index_cols] = rtf_veh_kms[index_cols].fillna(method="ffill")
    rtf_veh_kms.set_index(index_cols, inplace=True)
    rtf_veh_kms.columns = pd.to_numeric(rtf_veh_kms.columns, downcast="unsigned")

    data: pd.Series = rtf_veh_kms.loc["England", "All", "LGV"]
    data.name = "LGV Vehicle Kilometres (billions)"

    fit = _GrowthFactorLinRegress(data)
    return _calculate_growth_factors(fit, base_year, forecast_year, plot_path)


def calculate_fleet_projections_growth_factor(
    projections_path: pathlib.Path, base_year: int, forecast_year: int, plot_path: pathlib.Path
) -> dict[str, float]:
    data = pd.read_csv(projections_path, comment=CSV_COMMENT_CHARACTER, index_col=0)
    data.columns = pd.to_numeric(data.columns, downcast="unsigned")
    data.index = data.index.str.strip().str.upper()

    lgv_projections: pd.Series = data.loc["LGV"]
    lgv_projections.name = "LGV Fleet Growth Projections from NoCARB"

    # Growth factors are given as cumulative product relative increase
    # so need combining to calculate actual growth factors per year
    lgv_projections += 1
    lgv_projections = lgv_projections.cumprod()

    fit = _GrowthFactorLinRegress(lgv_projections)
    return _calculate_growth_factors(fit, base_year, forecast_year, plot_path)


def compare_column_totals(base: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    # TODO Docstring
    base.loc[:, "Rows"] = 1
    forecast.loc[:, "Rows"] = 1

    data = pd.concat([base.sum(numeric_only=True), forecast.sum(numeric_only=True)], axis=1)
    data.columns = ["Base", "Forecast"]

    data.loc[:, "Diff"] = data["Forecast"] - data["Base"]
    data.loc[:, "% Diff"] = (data["Forecast"] / data["Base"]) - 1

    return data


def main(params: ForecastInputsConfig) -> None:
    # TODO Docstring
    output_folder = (
        params.output_folder / f"LGV Forecast Inputs {params.forecast_year} "
        f"- {dt.date.today():%Y%m%d}"
    )
    output_folder.mkdir(exist_ok=True)

    details = caf.toolkit.ToolDetails("caf.van.forecast_inputs", caf.van.__version__)
    log_file = output_folder / "Forecast_inputs.log"
    with caf.toolkit.LogHelper("caf.van", details, log_file):
        LOG.info("Outputs saved to: %s", output_folder)

        out_path = output_folder / "forecast_inputs_config.yml"
        params.save_yaml(out_path)
        LOG.info("Written: %s", out_path.name)

        base_config = lgv_inputs.LGVInputPaths.load_yaml(params.base_model_config)
        out_path = output_folder / "base_inputs_config.yml"
        base_config.save_yaml(out_path)
        LOG.info("Written: %s", out_path.name)

        oa_lookup = load_oa_lookup(params.oa_lookup_path)
        growth = get_planning_growth(
            params.base_planning_path, params.forecast_planning_path, oa_lookup
        )

        growth_folder = output_folder / "growth_factors"
        growth_folder.mkdir(exist_ok=True)
        for name, data in growth:
            out_path = growth_folder / f"planning_data_growth_factors-{name}.csv"
            data.to_csv(out_path)
            LOG.info("Written: %s", out_path.relative_to(output_folder))

        forecast_paths: dict[str, Any] = {}
        totals_comparison: dict[str, pd.DataFrame] = {}

        grown_inputs_folder = output_folder / "grown_inputs"
        grown_inputs_folder.mkdir(exist_ok=True)

        forecast_paths["QS606_data"], comparisons = grow_occupation_data(
            base_config.qs606ew_path,
            base_config.qs606sc_path,
            growth,
            params.base_year,
            params.forecast_year,
            grown_inputs_folder,
        )
        totals_comparison.update({f"QS606{k}": v for k, v in comparisons.items()})

        forecast_paths["warehouse_data"], comparisons = grow_warehouse_data(
            base_config.warehouse_path,
            base_config.commute_warehouse_paths,
            growth,
            params.base_year,
            params.forecast_year,
            grown_inputs_folder,
        )
        totals_comparison.update(comparisons)

        forecast_paths = _recursive_apply(
            forecast_paths, lambda x: x.relative_to(output_folder)
        )

        growth_factors = calculate_veh_km_growth_factor(
            params.forecasted_vehicle_kms,
            params.base_year,
            params.forecast_year,
            output_folder / "LGV_growth_factor_plot.pdf",
        )
        forecast_paths.update({"Vehicle km based growth factors": growth_factors})
        growth_factors = calculate_fleet_projections_growth_factor(
            params.fleet_growth,
            params.base_year,
            params.forecast_year,
            output_folder / "LGV_fleet_projections_growth_factor_plot.pdf",
        )
        forecast_paths.update(
            {"NoCARB fleet projections based growth factors": growth_factors}
        )

        write_forecast_log(
            forecast_paths,
            output_folder / "grown_data.yml",
            params.base_year,
            params.forecast_year,
        )

        output_path = grown_inputs_folder / "grown_input_comparisons.xlsx"
        with pd.ExcelWriter(output_path, engine="openpyxl") as excel:
            for name, data in totals_comparison.items():
                data.to_excel(excel, sheet_name=name)
        LOG.info("Written summaries to: %s", output_path.relative_to(output_folder))


##### MAIN #####
if __name__ == "__main__":
    main(ForecastInputsConfig.load_yaml(CONFIG_PATH))
