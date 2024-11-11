""" script to combine, aggregate and rezone dvectors"""

import pathlib
import glob

import pandas as pd

import caf.base


def concat_dvecs(dir: pathlib.Path, out: pathlib.Path) -> None:
    lsoa_zoning = caf.base.ZoningSystem.get_zoning("lsoa_2021")

    paths = glob.glob(str(dir))
    dvecs: list[caf.base.DVector] = []
    for path in paths:

        print(f"reading {path}")
        dvecs.append(caf.base.DVector.load(path).aggregate(["accom_h"]))

    segmentation = dvecs[0].segmentation

    print("combining")
    data = pd.concat([d.data for d in dvecs], axis=1)
    data = data.fillna(0)
    # data[segmentation.names] = data[segmentation.names].astype(int)
    # data = data.groupby(segmentation.names).sum()
    data = data.rename(columns=lsoa_zoning.name_to_id)
    print("creating dvec")
    final_dvec = caf.base.DVector(
        import_data=data,
        segmentation=segmentation,
        zoning_system=lsoa_zoning,
    )
    print("saving")
    final_dvec.save(out_path=out)


def zone_dvec(in_path: str, out_path: str) -> None:
    lsoa_zoning = caf.base.ZoningSystem.get_zoning("lsoa_2021")

    dvec = caf.base.DVector.load(in_path)

    data = dvec.data
    segmentation = dvec.segmentation
    # data = data.rename(columns = lsoa_zoning.name_to_id)
    caf.base.DVector(
        import_data=data,
        segmentation=segmentation,
        zoning_system=caf.base.ZoningSystem.get_zoning("lsoa_2021"),
    )  # .save(out_path)


# zone_dvec(r"F:\Working\Land-Use\OUTPUTS_base_employment_inc_scotland_v2_voa_and_farmers_adjust\Output E5.hdf", r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\TfN-Land-Use-Pop\jobs.dvec")


concat_dvecs(
    pathlib.Path(
        r"F:\Working\Land-Use\DELIVERABLES\20241111_POPULATION\02_Final Outputs\*P11.1*.hdf"
    ),
    pathlib.Path(
        r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\TfN-Land-Use-Pop\occupied_dwellings_v2.dvec"
    ),
)
concat_dvecs(
    pathlib.Path(
        r"F:\Working\Land-Use\DELIVERABLES\20241111_POPULATION\01_Intermediate Files\*P11.2*.hdf"
    ),
    pathlib.Path(
        r"U:\Lot3_LFT\2.LGV Model\2024 - LGVN Rebase to 2023\inputs\TfN-Land-Use-Pop\unoccupied_dwellings_v2.dvec"
    ),
)
