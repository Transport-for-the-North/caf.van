from __future__ import annotations

import dataclasses
import pandas as pd
import caf.toolkit as ctk

# dft van statistics: https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fassets.publishing.service.gov.uk%2Fmedia%2F607724c2d3bf7f400cd5c1c9%2Fvan-statistics-2019-to-2020.ods&wdOrigin=BROWSELINK
# monthly TRA0305 & daily profiles TRA0308: https://www.gov.uk/government/statistical-data-sets/road-traffic-statistics-tra

TIME_LOOKUP = {
    "00:00 to 01:00": "OP",
    "01:00 to 02:00": "OP",
    "02:00 to 03:00": "OP",
    "03:00 to 04:00": "OP",
    "04:00 to 05:00": "OP",
    "05:00 to 06:00": "OP",
    "06:00 to 07:00": "OP",
    "07:00 to 08:00": "AM",
    "08:00 to 09:00": "AM",
    "09:00 to 10:00": "AM",
    "10:00 to 11:00": "IP",
    "11:00 to 12:00": "IP",
    "12:00 to 13:00": "IP",
    "13:00 to 14:00": "IP",
    "14:00 to 15:00": "IP",
    "15:00 to 16:00": "IP",
    "16:00 to 17:00": "PM",
    "17:00 to 18:00": "PM",
    "18:00 to 19:00": "PM",
    "19:00 to 20:00": "OP",
    "20:00 to 21:00": "OP",
    "21:00 to 22:00": "OP",
    "22:00 to 23:00": "OP",
    "23:00 to 00:00": "OP",
}


TIME_HOUR_LOOKUP = {"AM": 3, "IP": 6, "PM": 3, "OP": 12}
WEEKS_MONTH_LOOKUP = {
    "january": 4 + 3 / 7,
    "febuary": 4 + 0.25 / 7,
    "march": 4 + 3 / 7,
    "april": 4 + 2 / 7,
    "may": 4 + 3 / 7,
    "june": 4 + 2 / 7,
    "july": 4 + 3 / 7,
    "august": 4 + 3 / 7,
    "september": 4 + 2 / 7,
    "october": 4 + 3 / 7,
    "november": 4 + 2 / 7,
    "december": 4 + 3 / 7,
}

WEEKDAYS = ["tuesday", "wednesday", "thursday"]


class TimePeriodInputs(ctk.BaseConfig):
    van_stats_path: str
    day_distribution_path: str
    month_distribution_path: str
    month: str
    day: str
    year: int
    out_path: str

    def parse(self) -> TimePeriodParams:
        van_stats = pd.read_excel(
            self.van_stats_path,
            engine="odf",
            sheet_name="VAN0304",
            skiprows=6,
            skipfooter=13,
            names=[
                "frequency",
                "road_type",
                "service",
                "delivery",
                "private_domestic",
                "recreaction",
                "transport_to_others",
                "all",
            ],
        )
        van_stats = van_stats.fillna(method="ffill")

        van_stats = van_stats[
            van_stats["frequency"] == "Frequent Travel (at least 4 days per week)"
        ]
        van_stats = van_stats[["road_type", "service", "delivery", "private_domestic"]]

        day_distribution = pd.read_excel(
            self.day_distribution_path,
            engine="odf",
            sheet_name="TRA0308",
            skiprows=4,
            usecols=[0, 1, 2, 5, 6, 7, 8, 9, 10, 11],
            names=[
                "year",
                "time",
                "vehicle_type",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ],
        )

        day_distribution = day_distribution[day_distribution["year"] == self.year]
        day_distribution = day_distribution[
            day_distribution["vehicle_type"] == "Light Commercial Vehicles"
        ]

        day_distribution["time"] = day_distribution["time"].replace(TIME_LOOKUP)

        day_distribution["average_day"] = day_distribution[WEEKDAYS].mean(axis=1)

        day_distribution = day_distribution.groupby("time")["average_day"].sum()

        month_distribution = pd.read_excel(
            self.month_distribution_path,
            engine="odf",
            sheet_name="TRA0305b",
            skiprows=4,
            usecols=[0, 1, 2, 6],
            names=["year", "road_type", "month", "van_index"],
        )

        filtered_month_distribution = month_distribution[
            month_distribution["month"].str.lower() == self.month.lower()
        ]

        filtered_month_distribution = filtered_month_distribution[
            filtered_month_distribution["year"] == self.year
        ]
        filtered_month_distribution = filtered_month_distribution[
            filtered_month_distribution["road_type"] == "All roads"
        ]
        month_index = filtered_month_distribution["van_index"].squeeze()

        return TimePeriodParams(
            van_stats,
            day_distribution.to_dict(),
            month_index,
            WEEKS_MONTH_LOOKUP[self.month.lower()],
        )


@dataclasses.dataclass
class TimePeriodParams:
    van_road_distribution: pd.DataFrame
    day_time_profiles: dict[str, float]
    month_distribution: float
    weeks_in_month: float


def calculate_time_period_factors(
    day_time_profiles: dict, month_distribution: float, weeks_in_month
) -> pd.DataFrame:
    profiles = {}
    for tp, day_factor in day_time_profiles.items():
        profiles[tp] = (
            (month_distribution / (12 * 100))
            * (1 / weeks_in_month)
            * (day_factor / (100 * 7 * 24))
            * (1 / TIME_HOUR_LOOKUP[tp])
        )
    return pd.Series(profiles).to_frame("profile")


time_period_inputs = TimePeriodInputs.load_yaml(r"src\scripts\time_period_factors.yaml")
time_profile_inputs = time_period_inputs.parse()
time_profile = calculate_time_period_factors(
    time_profile_inputs.day_time_profiles,
    time_profile_inputs.month_distribution,
    time_profile_inputs.weeks_in_month,
)
time_profile.to_csv(time_period_inputs.out_path)
