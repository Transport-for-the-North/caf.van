# Third Party
import pandas as pd

NORMITS_LOOKUP = r"I:\Data\Zoning Systems\core_zoning\normits\zoning.csv"

COST_MATRIX = r"I:\NorMITs Supply\Base\voa_gb\CSVs\HWnet_cost_ave-distance.csv"

OUTPATH = r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\avg_cost_matrix_voa.csv"


def convert_to_normits(normits_path: str, cost_matrix_path: str, out_path: str):
    normits = pd.read_csv(normits_path)["zone_id"].sort_values().reset_index(drop=True)
    normits_cube_lookup = {k + 1: v for k, v in normits.to_dict().items()}
    cost_matrix = pd.read_csv(cost_matrix_path, index_col=0)
    cost_matrix.columns = [int(x) for x in cost_matrix.columns]
    cost_matrix = cost_matrix.rename(columns=normits_cube_lookup)
    cost_matrix = cost_matrix.rename(index=normits_cube_lookup)
    cost_matrix.to_csv(out_path)


convert_to_normits(NORMITS_LOOKUP, COST_MATRIX, OUTPATH)
