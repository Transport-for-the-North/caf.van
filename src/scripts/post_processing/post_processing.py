"""Creates a 'combined' matrix without personal included and translates to a new zone system."""  # noqa: E501 review required

# Built-Ins
import collections
import glob
import pathlib
from functools import reduce

# Third Party
import caf.toolkit as ctk
import pandas as pd

VOA_MATRIX_DIR = pathlib.Path(
    r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_VOA\time period matrices"  # noqa: E501 review required
)
NO_VOA_MATRIX_DIR = pathlib.Path(
    r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_no_VOA\time period matrices"  # noqa: E501 review required
)
VOA_OUTPATH = pathlib.Path(
    r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_VOA\tp_noham"  # noqa: E501 review required
)

NO_VOA_OUTPATH = pathlib.Path(
    r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\development_outputs\2023_NorMITs_no_VOA\tp_noham"  # noqa: E501 review required
)

SEGMENTS = ["combined", "service", "delivery", "commuting"]
TRANSLATION = r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\normits_v3.3_noham_v3.7_trans 1.csv"  # noqa: E501 review required


def process_matrices(  # noqa: C901 review required
    matrix_dir: pathlib.Path,
    segments: list[str],
    translation_path: pathlib.Path,
    output_path: pathlib.Path,
) -> None:
    """Processes matrices into a the output format."""  # noqa: D401 review required
    # path.glob(*)

    tp_dir = [x for x in matrix_dir.iterdir() if x.is_dir()]

    print(f"{len(tp_dir)} tps found")  # noqa: T201 review required

    for dir in tp_dir:  # noqa: A001 review required
        print(f"processing {dir}")  # noqa: T201 review required

        tp_output_dir = output_path / dir.stem

        tp_output_dir.mkdir(exist_ok=True, parents=True)

        # sort matrices
        matrix_paths = glob.glob(str(matrix_dir / dir / "*.csv"))  # noqa: PTH207 review required
        print(f"{len(matrix_paths)} matrices found")  # noqa: T201 review required
        sorted_matrices = collections.defaultdict(list)
        for path in matrix_paths:
            matrix = pd.read_csv(path, index_col=0)
            name: str = pathlib.Path(path).stem
            print(f"read {name}")  # noqa: T201 review required
            for seg in segments:
                if seg.lower() == "combined":
                    if "combined" in name.lower() or "personal" in name.lower():
                        print(f"leaving out {name} combined matrix")  # noqa: T201 review required
                        continue
                    print(f"Adding {name} to combined matrices")  # noqa: T201 review required
                    sorted_matrices[seg].append(matrix)
                    continue
                if seg.lower() in name.lower():
                    sorted_matrices[seg].append(matrix)

        # sum matrices

        collated_matrices = {}

        for seg_name, matrices in sorted_matrices.items():
            print(f"collating {seg_name}")  # noqa: T201 review required

            if len(matrices) == 0:
                raise ValueError(f"no matrices in segment {seg_name}")

            if len(matrices) == 1:
                collated_matrices[seg_name] = matrices[0]

            else:
                collated_matrices[seg_name] = reduce(lambda a, b: a.add(b), matrices)

        del sorted_matrices
        # translate

        translation = pd.read_csv(translation_path)

        translated = {}

        for name, matrix in collated_matrices.items():
            print(f"translating {name}")  # noqa: T201 review required
            translated[name] = ctk.translation.pandas_matrix_zone_translation(
                matrix,
                translation,
                "normits_v3.3_id",
                "noham_v3.7_id",
                "normits_v3.3_to_noham_v3.7_spatial",
            )

            translated[name].to_csv(tp_output_dir / f"{name}.csv")


process_matrices(VOA_MATRIX_DIR, SEGMENTS, TRANSLATION, VOA_OUTPATH)
process_matrices(NO_VOA_MATRIX_DIR, SEGMENTS, TRANSLATION, NO_VOA_MATRIX_DIR)
