from __future__ import annotations

import glob
import pathlib

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import caf.toolkit as ctk

from matplotlib.backends.backend_pdf import PdfPages


def create_plot(
    data: pd.DataFrame,
    geometry: gpd.GeoDataFrame,
    path: pathlib.Path,
    data_id_col: str,
    geom_id_col: str,
) -> None:

    data_cols = data.select_dtypes(include=[np.number]).columns.to_list()

    geo_data_df = geometry.merge(data, left_on=geom_id_col, right_on=data_id_col)

    geo_data = gpd.GeoDataFrame(geo_data_df)

    bounds = geo_data.total_bounds

    try:
        data_cols.remove(data_id_col)
    except ValueError:
        pass

    with PdfPages(path) as pdf:
        for col in data_cols:
            fig, ax = plt.subplots(figsize=(6, 9), layout="tight")
            ax.set_title(col)
            ax.get_xaxis().set_visible(False)
            ax.get_yaxis().set_visible(False)
            ax.set_aspect((bounds[2] - bounds[0]) / (bounds[3] - bounds[1]))
            geo_data.plot(col, legend=True, ax=ax, legend_kwds={"label": "Trips"})

            pdf.savefig()


def summarise_tlds(
    data_dir: pathlib.Path,
    geometry_path: pathlib.Path,
    translation_path: pathlib.Path,
    output_path: pathlib.Path,
) -> None:

    trip_end_paths = glob.glob(str(data_dir / "*.csv"))

    translation = pd.read_csv(translation_path)

    geom = gpd.read_file(geometry_path)

    geom["geometry"] = geom["geometry"].simplify(100)

    for path in trip_end_paths:
        file_name = pathlib.Path(path).stem + ".pdf"

        trip_end = pd.read_csv(path)

        translated_trip_ends = ctk.translation.pandas_vector_zone_translation(
            trip_end.set_index("Zone"), translation, "NTEM_id", "LAD_id", "NTEM_to_LAD"
        )

        create_plot(
            translated_trip_ends.reset_index(),
            geom,
            output_path / file_name,
            "LAD_id",
            "LAD21CD",
        )


summarise_tlds(
    pathlib.Path(
        r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\CAF.Van Model Outputs - 2024-10-02 20.51.43\trip ends"
    ),
    pathlib.Path(
        r"Y:\Data Strategy\GIS Shapefiles\Local_Authority_District_LAD\LAD_2021\LAD_MAY_2021_UK_BFE_V2.shp"
    ),
    pathlib.Path(
        r"U:\Lot3_LFT\2.LGV Model\LGV Model Inputs\0.Lookups\NTEM model run Lookups\LAD_NTEM_spatial_missing_zones_added.csv"
    ),
    pathlib.Path(r"F:\CAF_VAN_TEST\trip_end_plots"),
)
