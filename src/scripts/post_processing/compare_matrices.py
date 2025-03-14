# Built-Ins
import glob
import itertools
import pathlib
import re
from typing import Optional

# Third Party
import caf.toolkit as ctk
import numpy as np
import pandas as pd
from caf.toolkit import translation
from plotly import express as px
from plotly import graph_objects as go


def create_comparisons_path(
    comparisions: dict[str, str],
    suffix: str = "-GM_log",
) -> dict[str, dict[str, pathlib.Path]]:

    unpacked_files = {}
    for run_name, dir in comparisions.items():
        files = glob.glob(dir)
        labelled_files = {}
        for f in files:
            path = pathlib.Path(f)
            name = path.stem.removesuffix(suffix)
            if name == "commute_Skilled trades":
                name = "commute_skilled_trades"
            labelled_files[name] = path

        unpacked_files[run_name] = labelled_files

    comparisions = {}
    for run_name, files in unpacked_files.items():
        for matrix_name, path in files.items():
            try:
                comparisions[matrix_name][run_name] = path
            except KeyError:
                comparisions[matrix_name] = {run_name: path}

    return comparisions


def compare_matrices(comparision_paths: dict[str, pathlib.Path]) -> dict[str, pd.DataFrame]:
    comparisons = {}
    for name, path in comparision_paths.items():
        comparisons[name] = pd.read_excel(path, sheet_name="Matrix", index_col=0)

    if len(comparisons) == 1:
        return comparisons

    results = {**comparisons}  # Start with the original dictionary items
    keys = list(comparisons.keys())

    for combo in itertools.combinations(keys, 2):
        df1, df2 = comparisons[combo[0]], comparisons[combo[1]]
        results[f"{combo[0]}-{combo[1]}"] = df1 - df2
        results[f"{combo[0]}%{combo[1]}"] = df1 / df2

    return results


def compare_tlds(
    comparision_paths: dict[str, pathlib.Path],
    output_path: pathlib.Path,
) -> None:
    comparisons = {}

    for run_name, path in comparision_paths.items():

        all_sheets = pd.read_excel(path, None)

        for dist_name, sheet in all_sheets.items():

            if dist_name.startswith("Achieved Distribution"):

                if "from" in sheet.columns:
                    comparisons[f"{dist_name[-1]}_{run_name}"] = (
                        ctk.cost_utils.CostDistribution(
                            sheet,
                            min_col="from",
                            max_col="to",
                            avg_col="av_distance",
                            trips_col="normalised",
                        )
                    )

                else:
                    label = re.search(r"\d{1,2}$", dist_name).group()
                    comparisons[f"{label}_{run_name}"] = ctk.cost_utils.CostDistribution(sheet)
            elif dist_name.startswith("Target Distribution"):

                if "from" in sheet.columns:
                    comparisons[f"target_{dist_name[-1]}_{run_name}"] = (
                        ctk.cost_utils.CostDistribution(
                            sheet,
                            min_col="from",
                            max_col="to",
                            avg_col="av_distance",
                            trips_col="normalised",
                        )
                    )

                else:

                    comparisons[f"target_{dist_name[-1]}_{run_name}"] = (
                        ctk.cost_utils.CostDistribution(sheet)
                    )

    _plot_tlds(comparisons, output_path)


def compare_matrix_summaries(comparision_paths: dict[str, pathlib.Path]) -> pd.DataFrame:

    comparisons = None
    for name, path in comparision_paths.items():
        summary = pd.read_excel(path, sheet_name="Summary", index_col=0)
        summary.columns = [col + f"_{name}" for col in summary.columns]
        if comparisons is None:
            comparisons = summary
        else:
            comparisons = comparisons.join(summary)
    return comparisons


def create_trip_end_comparisions(dirs: dict[str, str], out_dir: pathlib.Path) -> pd.DataFrame:
    comparisons = create_comparisons_path(dirs, "_trip_ends")
    with pd.ExcelWriter(out_dir / "tripend_comparison.xlsx") as steve:
        for name, comp in comparisons.items():
            tripend_comparisons = compare_trip_ends(comp)
            tripend_comparisons.to_excel(steve, sheet_name=name)


def create_matrix_comparisons(dirs: dict[str, str], out_path: pathlib.Path):
    comparisons_files = create_comparisons_path(dirs)
    for name, comp in comparisons_files.items():
        matrix_comparisons = compare_matrices(comp)

        with pd.ExcelWriter(out_path / f"{name}_comparison.xlsx") as steve:
            for sheet_name, x in matrix_comparisons.items():
                x.to_excel(steve, sheet_name=sheet_name)

    with pd.ExcelWriter(out_path / "matrix_summary.xlsx") as steve:

        for name, comp in comparisons_files.items():
            matrix_summaries = compare_matrix_summaries(comp)

            matrix_summaries.to_excel(steve, sheet_name=name)

    for name, comp in comparisons_files.items():
        compare_tlds(comp, out_path / rf"tlds\{name}_tlds.html")


def create_sector_cost_matrix(
    cost_matrix: pd.DataFrame, translation_: pd.DataFrame, from_: str, to: str
) -> pd.DataFrame:
    translated = translation.pandas_matrix_zone_translation(
        cost_matrix,
        translation_,
        translation_from_col=f"{from_}_id",
        translation_to_col=f"{to}_id",
        translation_factors_col=f"{from_}_to_{to}",
    )
    denoms: dict[str, dict[str, float]] = {}
    for c in translation_[f"{to}_id"].unique():
        col_vals = {}
        for i in translation_[f"{to}_id"].unique():
            col_vals[i] = (translation_[f"{to}_id"] == i).sum() * (
                translation_[f"{to}_id"] == c
            ).sum()
        denoms[c] = col_vals

    denom_df = pd.DataFrame(denoms)

    average = translated / denom_df

    return average


def matrix_describe(
    matrix: pd.DataFrame | pd.Series, almost_zero: Optional[float] = None
) -> pd.Series:
    if almost_zero is None:
        almost_zero = 1 / matrix.size
    if isinstance(matrix, pd.DataFrame):
        data = matrix.stack()
    else:
        data = matrix
    info = data.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95])
    info["sum"] = matrix.sum().sum()
    info["zeros"] = (matrix == 0).sum().sum()
    info["almost_zeros"] = (matrix < almost_zero).sum().sum()
    info["NaNs"] = matrix.isna().sum().sum()
    return info


def compare_trip_ends(comp: dict[str, pathlib.Path]) -> pd.DataFrame:
    comparisons = {}
    for name, path in comp.items():
        comparisons[name] = pd.read_csv(path, index_col=0)

    if len(comparisons) == 1:
        return pd.DataFrame(comparisons)

    results = {}  # Start with the original dictionary items
    keys = list(comparisons.keys())

    for combo in itertools.combinations(keys, 2):
        df1, df2 = comparisons[combo[0]], comparisons[combo[1]]
        try:
            results[f"{combo[0]}_productions"] = matrix_describe(df1["Productions"], 0.1)
            results[f"{combo[1]}_productions"] = matrix_describe(df2["Productions"], 0.1)
            results[f"{combo[0]}_attractions"] = matrix_describe(df1["Attractions"], 0.1)
            results[f"{combo[1]}_attractions"] = matrix_describe(df2["Attractions"], 0.1)
        except KeyError:
            results[f"{combo[0]}_origins"] = matrix_describe(df1["Origins"], 0.1)
            results[f"{combo[1]}_origins"] = matrix_describe(df2["Origins"], 0.1)
            results[f"{combo[0]}_destinations"] = matrix_describe(df1["Destinations"], 0.1)
            results[f"{combo[1]}_destinations"] = matrix_describe(df2["Destinations"], 0.1)

    return pd.DataFrame(results)


def cost_matrix_comparison():
    with pd.ExcelWriter(
        r"C:\Users\KieranFishwick\OneDrive - Transport for the North\Documents\caf-van_rebase\comparisons\cost_matrix_comparison.xlsx"
    ) as bob:
        normits = create_sector_cost_matrix(
            pd.read_csv(
                r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\Highway Costs\CSVs\HWnet_cost_ave_distance_codes.csv",
                index_col=0,
            ),
            pd.read_csv(
                r"U:\Lot3_LFT\2.LGV Model\LGV Model Inputs\NorMITs Zone System 3.3\CA_sector_normits_v3_3\CA_sector_to_normits_v3_3_spatial.csv"
            ),
            "normits_v3_3",
            "CA_sector",
        )
        print("writing normits")
        normits.to_excel(bob, sheet_name="normits")
        print("calculating ntem")
        ntem = create_sector_cost_matrix(
            pd.read_csv(
                r"U:\Lot3_LFT\2.LGV Model\LGV Model Inputs\8.Cost Matrix\MSOA_Distance_up_to_tertiary_roads_infilled.csv",
                index_col=0,
            ),
            pd.read_csv(
                r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\NTEM_to_CA_spatial_missing_infilled.csv"
            ),
            "NTEM",
            "CA",
        )
        print("writing ntem")
        ntem.to_excel(bob, sheet_name="ntem")


def intra_mean(cost_matrix_path: str, sector_path: str):
    cost_matrix = pd.read_csv(cost_matrix_path, index_col=0)
    cost_matrix.columns = [int(c) for c in cost_matrix.columns]
    sectors = pd.read_csv(sector_path)
    alan = {}
    for s in sectors["area"].unique():
        steve = sectors.loc[sectors["area"] == s, "zone_id"]
        matrix_subset = cost_matrix.loc[steve, steve]
        bob = np.diag(matrix_subset)
        alan[s] = {"mean": np.mean(bob), "std": np.std(bob)}

    return pd.DataFrame(alan)


def _plot_tlds(tlds: dict[str, ctk.cost_utils.CostDistribution], output_path: pathlib.Path):
    tld_data = []
    for name, tld in tlds.items():
        data = pd.DataFrame(
            {
                "Name": name,
                "Distance (km)": tld.avg_vals,
                "Trip Proportion": tld.band_share_vals,
                "Trips": tld.trip_vals,
                "Bin Range (km)": [f"{i} - {j}" for i, j in zip(tld.min_vals, tld.max_vals)],
            }
        )
        tld_data.append(data)

    tld = pd.concat(tld_data)

    fig = px.line(
        tld,
        x="Distance (km)",
        y="Trip Proportion",
        color="Name",
        title="Trip Length Distributions for LGV matrices from caf.van",
        hover_name="Name",
        hover_data={
            "Name": False,
            "Bin Range (km)": True,
            "Distance (km)": ":,.0f",
            "Trip Proportion": ":.1%",
            "Trips": ":,.0f",
        },
        markers=True,
    )
    fig.update_layout(yaxis=go.layout.YAxis(tickformat=".0%"))

    fig.write_html(output_path, include_plotlyjs="cdn")


# rob = intra_mean(r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\Highway Costs\CSVs\HWnet_cost_ave_distance_codes.csv",r"U:\Lot3_LFT\2.LGV Model\LGV Model Inputs\NorMITs Zone System 3.3\area_to_NorMITs_zoning_v3.3.csv")
# print("stap")
# compare_trip_ends(
#    pathlib.Path(
#        r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs-full_LUR\trip ends\commute_Drivers_trip_ends.csv"
#    ),  # ]
#    pathlib.Path(
#        r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NTEM\trip ends\commute_Drivers_trip_ends.csv"
#    ),
# )


create_trip_end_comparisions(
    {
        "VOA_tld": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITS_VOA_GOR_calibrate\trip ends\*.csv",
        # "NorMITs_no_voa": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_no_VOA\trip ends\*.csv",
        "NorMITs_v2": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_LUR_v2_1\trip ends\*.csv",
        # "NorMITs_LUR": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs-full_LUR\trip ends\*.csv",
        # "NorMITs_census": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITS\trip ends\*.csv",
        # "NTEM": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NTEM\trip ends\*.csv",
    },
    pathlib.Path(
        r"C:\Users\KieranFishwick\OneDrive - Transport for the North\Documents\caf-van_rebase\comparisons\VOA_TLD"
    ),
)
create_matrix_comparisons(
    {
        "VOA_tld": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITS_VOA_GOR_calibrate\annual trip matrices\*-GM_log.xlsx",
        # "NorMITs_no_voa": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_no_VOA\annual trip matrices\*-GM_log.xlsx",
        "NorMITs_v2": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_LUR_v2_1\annual trip matrices\*-GM_log.xlsx",
        # "NorMITs_LUR": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs-full_LUR\annual trip matrices\*-GM_log.xlsx",
        # "NorMITs_census": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITS\annual trip matrices\*-GM_log.xlsx",
        # "NTEM": r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NTEM\annual trip matrices\*-GM_log.xlsx",
    },
    pathlib.Path(
        r"C:\Users\KieranFishwick\OneDrive - Transport for the North\Documents\caf-van_rebase\comparisons\VOA_TLD"
    ),
)

print("STAP")
