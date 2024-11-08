#!/usr/bin/env python

# Usage: ./format_data.py [play_by_play_YEAR.csv] [injuries_YEAR] [training / testing] [year]

import pandas as pd
from tabulate import tabulate

import warnings
import sys
import os

# Suppress all warnings
warnings.filterwarnings("ignore")


# HELPERS FOR CONSTRUCTION


def first_last_a(name):
    parts = name.split(" ", 1)
    return f"{parts[0][0]}.{parts[1]}"


def first_last_b(name):
    parts = name.split(" ", 1)
    return f"{parts[0][0:2]}.{parts[1]}"


# IMPORT DATA

try:
    play_by_play_df_path = sys.argv[1]
    injuries_df_path = sys.argv[2]
    training_or_testing_dir = sys.argv[3]
    year = sys.argv[4]
except IndexError:
    raise Exception(
        "Usage: ./format_data.py [play_by_play_YEAR.csv] [injuries_YEAR] [training / testing] [year]"
    )

if training_or_testing_dir != "testing" and training_or_testing_dir != "training":
    raise Exception(
        "Usage: ./format_data.py [play_by_play_YEAR.csv] [injuries_YEAR] [training / testing] [year]"
    )

play_df = pd.read_csv(play_by_play_df_path)
injury_df = pd.read_csv(injuries_df_path)


# CLEAN DATA

# Remove rows with bad injury values in the 'report_primary_injury' column
injury_df_cleaned = injury_df.dropna(subset=["report_primary_injury"])
injury_df_cleaned = injury_df_cleaned[
    injury_df_cleaned["report_primary_injury"]
    != "gameday concussion protocol evaluation"
]
injury_df_cleaned = injury_df_cleaned[
    injury_df_cleaned["report_primary_injury"] != "Not injury related - personal matter"
]

# List of values to remove based on the provided indices
values_to_remove = [
    "Being evaluated for a concussion",
    "Not injury related - other",
    "Being Evaluated for a Concussion",
    "Evaluated for a head injury and cleared to return",
    "Evaluated for a potential head injury and cleared to return.",
    "Evaluated for a head injury and cleared to return",
    "Update: Hall has been cleared to return.",
    "Player was ill this morning. Fully expected to play. No game status.",
    "Not injury related - resting player",
    "Evaluated for a possible head injury and cleared to return.",
]

# Remove specified values from the 'report_primary_injury' column
injury_df_cleaned = injury_df_cleaned[
    ~injury_df_cleaned["report_primary_injury"].isin(values_to_remove)
]

print("total rows in injury_df_cleaned: ", len(injury_df_cleaned))

# sanity check:
# Group by the 'report_primary_injury' column and count occurrences
primary_injury_counts = injury_df_cleaned["report_primary_injury"].value_counts()

# Print the counts of each unique value in a pretty table format
print("Counts of Primary Injury Data:")
print(
    tabulate(
        primary_injury_counts.reset_index(),
        headers=["Primary Injury", "Count"],
        tablefmt="pretty",
    )
)

num_columns = play_df.shape[1]
print("Number of columns in play_df: ", num_columns)
column_names = play_df.columns.tolist()
# print(column_names)


# CONSTRUCT DATA

injury_df["date"] = pd.to_datetime(injury_df["date_modified"])
play_df["date"] = pd.to_datetime(play_df["game_date"])
injury_df["date"] = injury_df["date"].dt.tz_localize(None)
play_df["date"] = play_df["date"].dt.tz_localize(None)

plays_with_injuries = play_df[play_df["desc"].str.contains("was injured", na=False)]

pattern = r"(\w+\.(?:\w|-|\.|\')+(?: \w+)*) was injured"
# Extract the injured player's name from the desc column
injured_players = plays_with_injuries.loc[:, "desc"].str.extract(pattern)
# print(injured_players.drop(injured_players.columns[1], axis=1))
# print(injured_players)

plays_with_injuries = pd.concat([plays_with_injuries, injured_players], axis=1)
plays_with_injuries.rename(columns={0: "injured_player"}, inplace=True)

injuries = []
for (week, team), group_injury_df in injury_df.groupby(["week", "team"]):
    group_play_df = plays_with_injuries[
        (plays_with_injuries["week"] == week)
        & (
            (plays_with_injuries["home_team"] == team)
            | (plays_with_injuries["away_team"] == team)
        )
    ]

    group_injury_df = group_injury_df[group_injury_df.date >= group_play_df.date.max()]

    group_injury_df["first_type"] = group_injury_df["full_name"].apply(first_last_a)
    group_injury_df["second_type"] = group_injury_df["full_name"].apply(first_last_b)

    x = pd.merge(
        group_play_df,
        group_injury_df,
        left_on="injured_player",
        right_on="first_type",
        how="inner",
    )
    y = pd.merge(
        group_play_df,
        group_injury_df,
        left_on="injured_player",
        right_on="second_type",
        how="inner",
    )

    injuries.append(pd.concat([x, y], axis=0, ignore_index=True))

plays_with_injuries_and_injury_record = (
    pd.concat(injuries, axis=0, ignore_index=True)
).drop(columns=["first_type", "second_type"])

plays_with_injuries_and_injury_record = (
    plays_with_injuries_and_injury_record.sort_values(
        "play_id", ascending=False
    ).drop_duplicates(subset=["week_x", "full_name", "team"], keep="first")
)

# bins = [-28, -0.1, 0.1, 30]
# labels = ["Trailing", "Tied", "Leading"]

# plays_with_injuries_and_injury_record["score_differential_binned"] = pd.cut(
#     plays_with_injuries_and_injury_record["score_differential"],
#     bins=bins,
#     labels=labels,
#     include_lowest=True,
# )


# WRITE TO FILES
plays_with_injuries_and_injury_record.to_csv(
    f"{os.getcwd()}/preprocessed_data/{training_or_testing_dir}/plays_with_injuries_and_injury_record_{year}.csv",
    index=False,
)
