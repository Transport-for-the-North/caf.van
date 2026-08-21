"""Perform some validation and checking of the van model inputs."""

##### IMPORTS #####

# Built-Ins
import logging
import pathlib
import re
import shutil
import warnings

# Third Party
import caf.base as cbase
import caf.toolkit as ctk
import numpy as np
import pandas as pd
import pydantic

# Local Imports
from caf.van import lgv_inputs

##### CONSTANTS #####

_NAME = pathlib.Path(__file__).stem
LOG = logging.getLogger(_NAME)
_CONFIG_FILE = pathlib.Path(__file__).with_suffix(".yml")
MOVE_LOOKUPS_TO_OUTPUTS = False


##### CLASSES & FUNCTIONS #####


class _Config(ctk.BaseConfig):
    caf_van_config: pydantic.FilePath
    output_folder: pydantic.DirectoryPath


class _ZoningSystemRetriever:
    """Get zoning system."""

    def __init__(self, folder: pathlib.Path = cbase.zoning.ZONE_CACHE_HOME) -> None:
        self._folder = folder
        self._systems = {}

    def get(self, name: str) -> cbase.ZoningSystem:
        """Retrieve zoning system."""
        if name in self._systems:
            return self._systems[name]

        zoning = cbase.ZoningSystem.get_zoning(name)
        self._systems[name] = zoning
        return zoning


def find_zoning_systems(folder: pathlib.Path) -> dict[str, pathlib.Path]:
    """Find zoning systems."""
    LOG.info('Searching for zone systems in "%s"', folder)
    systems = {}
    for path in folder.iterdir():
        # TODO Allow zone systems to be loaded from zip archives  # noqa: E501, TD002, TD003, TD004
        if not path.is_dir():
            continue

        missing = False
        for filename in ("zoning.csv", "zoning_meta.yml"):
            filepath = path / filename
            if not filepath.is_file():
                warnings.warn(
                    f"Found zoning system folder ({path.name}) without {filename}",
                    stacklevel=2,
                )
                missing = True

        if not missing:
            systems[path.name] = path

    return systems


def main() -> None:
    """Main function for inputs validation."""  # noqa: D401 review required
    parameters = _Config.load_yaml(_CONFIG_FILE)

    log_file = parameters.output_folder / f"{_NAME}.log"
    details = ctk.ToolDetails(_NAME, "0.1.0")

    with ctk.LogHelper(_NAME, details, log_file=log_file):
        LOG.debug("Input parameters:\n%s", parameters.to_yaml())
        parameters.save_yaml(parameters.output_folder / _CONFIG_FILE.name)

        LOG.info("Loading van config: %s", parameters.caf_van_config)
        van_config = lgv_inputs.LGVInputPaths.load_yaml(parameters.caf_van_config)

        find_zoning_systems(cbase.zoning.ZONE_CACHE_HOME)

        zoning_systems = _ZoningSystemRetriever()
        to_zone = zoning_systems.get("normits")

        _check_all_zone_lookups(parameters, van_config, zoning_systems, to_zone)
        _check_gm_area_lookups(van_config, to_zone)

        # Check cost matrix
        LOG.info("Checking cost matrix %s", van_config.cost_matrix_path.name)
        cost_matrix = ctk.io.read_csv_matrix(van_config.cost_matrix_path, "square")
        _check_zones("cost_matrix_index", to_zone, cost_matrix.index.to_numpy())

        # Check constructions
        LOG.info("Checking construction data %s", van_config.constructions_path)
        constructions = pd.read_csv(
            van_config.constructions_path,
            usecols=[
                "zone",
                "additional_dwellings",
                "demolished_dwellings",
                "business_floorspace",
            ],
        )
        _check_zones("constructions_zones", to_zone, constructions["zone"].to_numpy())
        LOG.info("Constructions info:\n%s", constructions.describe())


def _check_all_zone_lookups(
    parameters: _Config,
    van_config: lgv_inputs.LGVInputPaths,
    zoning_systems: _ZoningSystemRetriever,
    to_zone: cbase.ZoningSystem,
) -> None:
    zone_lookups = [
        (van_config.lsoa_lookup_path, "lsoa_2011"),
        (van_config.summary_zone_translation.path, "ca_sector_2020"),
        (van_config.household_paths.zc_path, "lsoa_2021"),
        (van_config.employment_paths.zc_path, "lsoa_2021"),
    ]

    for path, name in zone_lookups:
        if MOVE_LOOKUPS_TO_OUTPUTS:
            LOG.info("Copying %s to %s", path.name, parameters.output_folder)
            shutil.copy(path, parameters.output_folder)

        LOG.info("Checking %s", path.name)
        try:
            from_zone = zoning_systems.get(name)
        except FileNotFoundError:
            warnings.warn(
                f"Cannot find zone system {name}, those zones"
                f" will not be checked fully for {path.name}",
                stacklevel=2,
            )
            from_zone = None

        lookup = pd.read_csv(path)

        to_zone_id, to_zone_name = _find_id_column(to_zone.name, lookup)
        from_zone_id, from_zone_name = _find_id_column(name, lookup)

        _check_zone_lookup(lookup, to_zone_id, to_zone, f"{to_zone_name}_to_{from_zone_name}")
        _check_zone_lookup(
            lookup, from_zone_id, from_zone, f"{from_zone_name}_to_{to_zone_name}"
        )


def _check_gm_area_lookups(
    van_config: lgv_inputs.LGVInputPaths, to_zone: cbase.ZoningSystem
) -> None:
    gm_segments = [
        "service",
        "delivery_parcel_stem",
        "commuting_drivers",
        "commuting_skilled_trades",
    ]
    for segment in gm_segments:
        try:
            params: lgv_inputs.GMInputs = getattr(van_config, segment)
        except AttributeError:
            continue

        if params.cat_zone_correspondance_path is None:
            continue

        LOG.info(
            "Checking area lookup for %s from %s",
            segment,
            params.cat_zone_correspondance_path.name,
        )
        area_lookup = pd.read_csv(
            params.cat_zone_correspondance_path, usecols=["area", "zone_id"]
        )
        _check_zones("zone_id", to_zone, area_lookup["zone_id"].to_numpy())


def _check_zone_lookup(
    lookup: pd.DataFrame, id_column: str, zoning: cbase.ZoningSystem | None, factor_col: str
) -> None:
    if zoning is not None:
        lookup_zones = lookup[id_column].unique()
        _check_zones(id_column, zoning, lookup_zones)

    factors = lookup.groupby(id_column)[factor_col].sum()

    if not np.allclose(factors, 1):
        warnings.warn(
            f"{np.sum(np.isclose(factors, 1))} zones have factors"
            f" ({factor_col}) which don't some to 1.0 for {id_column}",
            stacklevel=2,
        )
    else:
        LOG.info("Factors for %s zone translation all sum to 1.0", factor_col)


def _check_zones(id_column: str, zoning: cbase.ZoningSystem, lookup_zones: np.ndarray) -> None:
    missing = lookup_zones[~np.isin(lookup_zones, zoning.zone_ids)]
    additional = zoning.zone_ids[~np.isin(zoning.zone_ids, lookup_zones)]

    if len(missing) == len(zoning.zone_ids) and len(additional) == len(lookup_zones):
        # Check if zone names are used instead of IDs
        new_missing = lookup_zones[~np.isin(lookup_zones, zoning.zone_names())]
        if len(new_missing) < len(missing):
            missing = new_missing
            additional = zoning.zone_ids[~np.isin(zoning.zone_names(), lookup_zones)]
        else:
            del new_missing

    if len(missing) > 0:
        warnings.warn(
            f"{len(missing)} zones missing from {id_column} column in zone correspondence",
            stacklevel=2,
        )
    else:
        LOG.info("No zones missing from %s column in zone correspondence", id_column)

    if len(additional) > 0:
        warnings.warn(
            f"{len(additional)} zones found in {id_column} in zone"
            f" translation which aren't in the zone system {zoning.name}",
            stacklevel=2,
        )
    else:
        LOG.info("No additional zones found in %s column in zone correspondence", id_column)


def _find_id_column(
    zone_name: str, lookup: pd.DataFrame, retry: bool = True
) -> tuple[str, str]:
    id_pattern = re.compile(rf"^\s*({zone_name}.*)_id\s*$", re.IGNORECASE)

    id_column = list(filter(lambda x: x is not None, map(id_pattern.match, lookup.columns)))

    if len(id_column) == 0 and retry:
        # Remove any numbers (year / version) from the end of the name
        zone_name = re.sub(r"[_\d]+$", "", zone_name, flags=re.IGNORECASE)
        return _find_id_column(zone_name, lookup, False)

    if len(id_column) != 1:
        raise KeyError(f"found {len(id_column)} ID columns, expected 1")

    assert id_column[0] is not None  # noqa: S101 review required

    return id_column[0].group(0), id_column[0].group(1)


##### MAIN #####
if __name__ == "__main__":
    main()
