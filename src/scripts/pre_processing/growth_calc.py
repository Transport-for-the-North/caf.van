"""this is how we calculated the growth factors, feel free to use different data/methods to do your own, or don't."""  # noqa: D404, E501 review required

# Built-Ins
import pathlib
import re

# Third Party
import pandas as pd
from caf.toolkit import translation

# Local Imports
from caf.van import errors, utilities

E_DWELLINGS_NEW_COLS = {"Current\nONS code": "zone"}
E_DWELLINGS_HEADER = [
    "Current\nONS code",
    "Lower and Single Tier Authority Data",
    "Demolitions",
    "Net Additions",
]

BUSINESS_FLOORSPACE_HEADER: dict[str, type] = {"AREA_CODE": str}
BUSINESS_FLOORSPACE_RENAME = {"AREA_CODE": "zone"}
BUSINESS_CATEGORIES = ["Retail", "Office", "Industrial", "Other"]
BUSINESS_FLOORSPACE_REMOVE_ROWS = ["K", "E9", "W9", "E1"]

SCOT_WALES_DWELLINGS = {
    "path": pathlib.Path(
        r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\land-use\scotland_wales_dwellings_2023.csv"  # noqa: E501 review required
    ),
    "zc": pathlib.Path(
        r"I:\Data\Zone Translations\cache\LAD19_normits_v3_3\LAD19_to_normits_v3_3_spatial.csv"
    ),
}
ENGLAND_DWELLINGS = {
    "path": pathlib.Path(
        r"U:\Lot3_LFT\2.LGV Model\LGV Model Inputs\6.Dwellings Data\Live_table_123_2022_23_infilled.xlsx"  # noqa: E501 review required
    ),
    "zc": pathlib.Path(
        r"I:\Data\Zone Translations\cache\LAD18_normits_v3_3\LAD18_to_normits_v3_3_spatial.csv"
    ),
}
NDR_FLOORSPACE = {
    "path": pathlib.Path(
        r"U:\Lot3_LFT\2.LGV Model\LGV Model Inputs\7.Business Floorspace\NDR_business_floorspace_2023.csv"  # noqa: E501 review required
    ),
    "zc": pathlib.Path(
        r"I:\Data\Zone Translations\cache\LAD18_normits_v3_3\LAD18_to_normits_v3_3_spatial.csv"
    ),
}


def generate_construction(
    sw_dwellings_path: dict[str, pathlib.Path],
    e_dwellings_path: dict[str, pathlib.Path],
    ndr_floorspace_path: dict[str, pathlib.Path],
    model_year: int,
) -> pd.DataFrame:
    """Generate construction data input for caf.Van."""
    sw_dwellings, _ = read_sc_w_dwellings(sw_dwellings_path["path"], model_year)
    sw_dwellings = translation.pandas_vector_zone_translation(
        sw_dwellings.set_index("zone"),
        pd.read_csv(sw_dwellings_path["zc"]),
        "LAD19_id",
        "normits_v3_3_id",
        "LAD19_to_normits_v3_3",
    )
    ndr_floorspace, _ = read_ndr_floorspace(ndr_floorspace_path["path"], model_year)
    ndr_floorspace = translation.pandas_vector_zone_translation(
        ndr_floorspace.set_index("zone"),
        pd.read_csv(ndr_floorspace_path["zc"]),
        "LAD18_id",
        "normits_v3_3_id",
        "LAD18_to_normits_v3_3",
    )
    e_dwellings, _ = read_english_dwellings(e_dwellings_path["path"], model_year)
    e_dwellings = translation.pandas_vector_zone_translation(
        e_dwellings.set_index("zone"),
        pd.read_csv(e_dwellings_path["zc"]),
        "LAD18_id",
        "normits_v3_3_id",
        "LAD18_to_normits_v3_3",
    )

    england_growth = e_dwellings.join(ndr_floorspace, how="left")

    england_growth = england_growth.rename(
        columns={
            "Net Additions": "additional_dwellings",
            "Demolitions": "demolished_dwellings",
            "floorspace": "business_floorspace",
        }
    )

    # Calculate ratio of additional construction over net additional dwellings
    england_demo_factor = (
        england_growth["demolished_dwellings"].sum()
        / england_growth["additional_dwellings"].sum()
    )

    england_floorspace_factor = (
        england_growth["business_floorspace"].sum()
        / england_growth["additional_dwellings"].sum()
    )

    # Calculate additional construction
    sw_dwellings.loc[:, "additional_dwellings"] = (
        sw_dwellings.loc[:, str(model_year)] - sw_dwellings.loc[:, str(model_year - 1)]
    )

    sw_dwellings["demolished_dwellings"] = (
        sw_dwellings["additional_dwellings"] * england_demo_factor
    )

    sw_dwellings["business_floorspace"] = (
        sw_dwellings["additional_dwellings"] * england_floorspace_factor
    )

    # Concatenate the dwellings data
    cols = ["additional_dwellings", "demolished_dwellings", "business_floorspace"]

    return england_growth[cols] + sw_dwellings[cols]


def read_sc_w_dwellings(path: pathlib.Path, model_year: int) -> tuple[pd.DataFrame, list[str]]:
    """Read in scotland/wales dwellings data."""
    data_columns = [str(model_year - i) for i in (0, 1)]
    sc_w_header = {"zone": str, **dict.fromkeys(data_columns, int)}
    sc_w_dwellings = utilities.read_csv(path, columns=sc_w_header)
    return sc_w_dwellings, data_columns


def read_ndr_floorspace(
    path: pathlib.Path,
    model_year: int,
    rename_columns: dict[str, str] = BUSINESS_FLOORSPACE_RENAME,
) -> tuple[pd.DataFrame, list[str]]:
    """Read in NDR floorspace data."""
    zone_col = "AREA_CODE"
    columns = BUSINESS_FLOORSPACE_HEADER.copy()

    data_columns = {}
    for column_start in [
        f"Floorspace_{model_year - 1}-{str(model_year)[2:]}_",
        f"Floorspace_{model_year}-{str(model_year + 1)[2:]}_",
    ]:
        for category in BUSINESS_CATEGORIES:
            data_columns[column_start + category] = float
    columns.update(data_columns)

    ndr = utilities.read_csv(path, columns=columns).rename(columns=rename_columns)

    if zone_col in rename_columns:
        zone_col = rename_columns[zone_col]

    # Remove rows that are not LAD
    conditional = ndr[zone_col].str.startswith(BUSINESS_FLOORSPACE_REMOVE_ROWS[0])
    for row in BUSINESS_FLOORSPACE_REMOVE_ROWS[1:]:
        conditional = conditional | ndr[zone_col].str.startswith(row)
    ndr = ndr[~conditional]

    previous_yr = [col for col in ndr.columns if str(model_year - 1) in col]
    current_yr = [col for col in ndr.columns if str(model_year) in col]

    # sort lists alphabetically to ensure they are in the same category order
    previous_yr.sort()
    current_yr.sort()

    # Calculate floorspace differences
    for i, col in enumerate(current_yr):
        ndr.loc[:, f"{col.split('_')[-1]}"] = (
            ndr.loc[:, col] - ndr.loc[:, previous_yr[i]]
        ).abs()

    # Sum all differences
    ndr["floorspace"] = ndr[BUSINESS_CATEGORIES].sum(axis=1)

    # only include relevant columns
    ndr = ndr[["zone", "floorspace"]]

    return ndr, list(data_columns.keys())


def read_english_dwellings(
    path: pathlib.Path,
    model_year: int,
    rename_columns: dict[str, str] = E_DWELLINGS_NEW_COLS,
    drop_lad_name: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """Read in england dwelling data."""
    sheet = f"{model_year}-{model_year - 2000 + 1}"
    dwellings = (
        utilities.read_excel(
            path,
            columns=E_DWELLINGS_HEADER,
            skiprows=3,
            sheet_name=sheet,
        )
        .dropna(axis=1, how="all")
        .dropna(axis=0, how="any")
        .rename(columns=rename_columns)
    )

    if drop_lad_name:
        dwellings = dwellings.drop(axis=1, labels=["Lower and Single Tier Authority Data"])

    data_columns = ["Demolitions", "Net Additions"]
    for col in data_columns:
        try:
            dwellings.loc[:, col] = dwellings[col].astype(float)
        except ValueError as err:
            match = re.match(r"could not convert \w+ to float", str(err), re.IGNORECASE)
            if match:
                raise errors.NonNumericDataError(  # noqa: B904 review required
                    name=f"{path.stem} column", non_numeric=str(col)
                )
            raise

    return dwellings, data_columns


constructions = generate_construction(
    SCOT_WALES_DWELLINGS, ENGLAND_DWELLINGS, NDR_FLOORSPACE, 2023
)
constructions.index.name = "zone"
constructions.to_csv(
    r"U:\Lot3_LFT\2.LGV Model\LGV Model Inputs\constructions_normits_v3_3.csv"
)
