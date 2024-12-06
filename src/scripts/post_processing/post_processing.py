import collections
from functools import reduce
import glob
import os
import pathlib
import pandas as pd
import caf.toolkit as ctk

MATRIX_DIR = pathlib.Path(
    r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_VOA\time period matrices"
)
OUTPATH = pathlib.Path(
    r"C:\Users\KieranFishwick\OneDrive - Transport for the North\Documents\caf-van_rebase\processed_tp\2023_NoHAM_VOA"
)
SEGMENTS = ["combined", "service", "delivery", "commute"]
TRANSLATION = r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\normits_v3.3_noham_v3.7_trans 1.csv"


def process_matrices(
    matrix_dir: pathlib.Path,
    segments: list[str],
    translation_path: pathlib.Path,
    output_path: pathlib.Path,
) -> None:
    tp_dir = os.listdir(matrix_dir)
    print(f"{len(tp_dir)} tps found")

    for dir in tp_dir:

        print(f"processing {dir}")

        tp_output_dir = output_path/dir

        tp_output_dir.mkdir(exist_ok=True, parents=True)


        # sort matrices
        matrix_paths = glob.glob(str(matrix_dir / dir / "*.csv"))
        print(f"{len(matrix_paths)} matrices found")
        sorted_matrices = collections.defaultdict(lambda: [])
        for path in matrix_paths:
            matrix = pd.read_csv(path, index_col=0)
            name = pathlib.Path(path).stem
            print(f"read {name}")
            for seg in segments:
                if seg.lower() == "combined":
                    sorted_matrices[seg].append(matrix)
                    continue
                elif seg.lower() in name.lower():
                    sorted_matrices[seg].append(matrix)

        # sum matrices

        collated_matrices = {}

        for seg_name, matrices in sorted_matrices.items():
            print(f"collating {seg_name}")

            if len(matrices) == 0:
                raise ValueError(f"no matrices in segment {seg_name}")

            elif len(matrices) == 1:
                collated_matrices[seg_name] = matrices[0]

            else:
                collated_matrices[seg_name] = reduce(lambda a, b: a.add(b), matrices)

        del sorted_matrices
        # translate

        translation = pd.read_csv(translation_path)

        for name, matrix in collated_matrices.items():
            print(f"translating {name}")
            translation[name] = ctk.translation.pandas_matrix_zone_translation(
                matrix,
                translation,
                "normits_v3.3_id",
                "noham_v3.7",
                "normits_v3.3_to_noham_v3.7_spatial",
            )

            translation[name].to_csv(tp_output_dir/ f"{name}.csv")

        
process_matrices(MATRIX_DIR,SEGMENTS, TRANSLATION, OUTPATH)