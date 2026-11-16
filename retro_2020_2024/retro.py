# retro.py
# Retrospective study: dinoflagellate cell counts at the CalHABMAP sites, 2020-2024.
# Run it with:  python retro.py
#
# Step 1: download every dataset and print an inventory.
# Step 2: flag every site x date and write flags.csv.

import io
import re
import urllib.error
import urllib.request

import pandas as pd

# ---------------------------------------------------------------
# Settings (change these here, nowhere else)
# ---------------------------------------------------------------
ERDDAP_URL = "https://erddap.sccoos.org/erddap/tabledap/"

DATASETS = [
    "HABs-BodegaMarineLabBuoy",
    "HABs-BodegaMarineLab",
    "HABs-CalPolyPier",
    "HABs-Humboldt",
    "HABs-HumboldtSouthBay",
    "HABs-InnerTomalesBay",
    "HABs-MontereyWharf",
    "HABs-MorroBayBackBay",
    "HABs-MorroBayFrontBay",
    "HABs-NewportBeachPier",
    "HABs-SantaCruzWharf",
    "HABs-SantaMonicaPier",
    "HABs-ScrippsPier",
    "HABs-StearnsWharf",
    "HABs-TomalesBayMid-ChannelBuoy",
    "HABs-TomalesBayMouth",
    "HABs-TrinidadPier",
]

GENERA = [
    "Akashiwo_sanguinea",
    "Lingulodinium_polyedra",
    "Prorocentrum_spp",
    "Ceratium_spp",
    "Cochlodinium_spp",
    "Other_Dinoflagellates",
]

START = "2020-01-01"   # first day included (California date)
END = "2025-01-01"     # first day NOT included, so 2024-12-31 is the last day
TIMEZONE = "America/Los_Angeles"

# The label on the left becomes part of the column names in flags.csv
# (flag_1e4, genera_1e4...). If you change a number, change its label too.
THRESHOLDS = {"1e4": 10_000, "1e6": 1_000_000}

FLAGS_FILE = "flags.csv"   # written in the folder you run the script from
SUMMARY_FILE = "summary.csv"
FLAG_NAMES = ["EXCEEDS", "MISSING", "NO_EXCEEDANCE"]

def utc_text(day):
    """Turn a California date like "2020-01-01" into the UTC time text ERDDAP expects."""
    # Midnight in California on that day...
    local_midnight = pd.Timestamp(day, tz=TIMEZONE)
    # ...is 08:00 UTC in winter (07:00 UTC in summer).
    return local_midnight.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def build_url(dataset_id):
    """The web address for one dataset: time + the 6 genera, between START and END."""
    columns = "time," + ",".join(GENERA)
    # %3E means ">" and %3C means "<". ERDDAP needs them written this way in a URL.
    time_filter = "&time%3E=" + utc_text(START) + "&time%3C" + utc_text(END)
    return ERDDAP_URL + dataset_id + ".csv?" + columns + time_filter


def download(dataset_id):
    """Download one dataset and return it as a table.

    The table is empty if the dataset has no samples between START and END.
    If ERDDAP refuses the request (for example, a missing column), this raises
    an error that contains ERDDAP's own explanation.
    """
    url = build_url(dataset_id)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        # ERDDAP explains the problem inside its error page, in a line like:
        #   message="Not Found: Your query produced no matching results.";
        body = error.read().decode("utf-8", errors="replace")
        found = re.search(r'message="(.*?)";', body, re.DOTALL)
        if found:
            message = found.group(1)
        else:
            message = body[:200]

        # "No matching results" only means: no samples in this time range.
        # That is not an error, so we return an empty table.
        if "no matching results" in message.lower():
            return pd.DataFrame(columns=["time"] + GENERA)

        raise RuntimeError(f"HTTP {error.code}: {message}")

    # Same as data.py: line 2 of the file holds the units, so skip it.
    return pd.read_csv(io.StringIO(text), skiprows=[1])


def clean(df):
    """Convert the columns to dates and numbers, and turn negative values into NaN.

    Returns two things: the cleaned table, and how many negative values were found.
    """
    df = df.copy()

    # ERDDAP times are in UTC (the "Z" at the end of "2020-01-06T19:00:00Z").
    df["time"] = pd.to_datetime(df["time"], utc=True)

    # The calendar date in California. A sample taken at 5 pm in summer is
    # already the next day in UTC, so we convert to California time first.
    df["date"] = df["time"].dt.tz_convert(TIMEZONE).dt.date

    n_negative = 0
    for genus in GENERA:
        # Text that is not a number becomes NaN (same as data.py).
        df[genus] = pd.to_numeric(df[genus], errors="coerce")

        # A negative cell count is impossible, so it is not a valid value.
        negative = df[genus] < 0
        n_negative = n_negative + int(negative.sum())
        # .loc[rows, column] = value  sets those cells only.
        df.loc[negative, genus] = float("nan")

    df = df.sort_values("time")
    return df, n_negative


def all_weeks():
    """Every week (Monday to Sunday) that has at least one day between START and END."""
    last_day = pd.Timestamp(END) - pd.Timedelta(days=1)
    # freq="W" means weeks that end on Sunday, so each week is Monday-Sunday.
    return pd.period_range(START, last_day, freq="W")


def inventory_row(dataset_id, df, n_negative):
    """One row of the inventory table, as a dictionary: column name -> value."""
    row = {}
    row["dataset"] = dataset_id
    row["first_date"] = df["date"].min()   # NaN if there are no samples
    row["last_date"] = df["date"].max()
    row["n_samples"] = len(df)

    # How many dates have more than one sample.
    # value_counts() counts how many rows each date has.
    samples_per_date = df["date"].value_counts()
    row["n_duplicate_dates"] = int((samples_per_date > 1).sum())

    # Weeks with no row at all. These gaps never show up as MISSING later,
    # because there is no row to flag.
    sampled_weeks = pd.to_datetime(df["date"]).dt.to_period("W")
    weeks = all_weeks()
    row["n_weeks_without_sample"] = int((~weeks.isin(sampled_weeks)).sum())

    row["n_negative"] = n_negative

    # NaN count for each genus ("not counted").
    for genus in GENERA:
        row["nan_" + genus] = int(df[genus].isna().sum())

    return row


def merge_duplicate_dates(df):
    """Make one row per date. If a date has several samples, keep the highest value of each genus.

    max() skips NaN, so a genus counted in only one of the samples keeps that count,
    and a genus that is NaN in all of them stays NaN.
    """
    return df.groupby("date", as_index=False)[GENERA].max()


def flag_one_sample(values, threshold):
    """Flag one sample. values = the 6 genus values of that sample.

    Returns two things: the flag, and the genera above the threshold
    joined with ";" (empty text if none).
    """
    # notna() is True for every genus that was counted. sum() counts the Trues.
    if values.notna().sum() == 0:
        return "MISSING", ""

    # The genera above the threshold. A NaN value gives False, so it is never included.
    above = [genus for genus in GENERA if values[genus] > threshold]

    if len(above) > 0:
        return "EXCEEDS", ";".join(above)
    return "NO_EXCEEDANCE", ""


def flag_rows(site, df):
    """One dictionary per date of one site: the columns of flags.csv."""
    rows = []
    # iterrows() goes through the table one row at a time.
    for _, sample in df.iterrows():
        values = sample[GENERA]

        row = {"site": site, "date": sample["date"]}
        for genus in GENERA:
            row[genus] = values[genus]
        row["n_counted"] = int(values.notna().sum())

        # Each threshold separately: flag_1e4, genera_1e4, flag_1e6, genera_1e6
        for label, threshold in THRESHOLDS.items():
            flag, genera = flag_one_sample(values, threshold)
            row["flag_" + label] = flag
            row["genera_" + label] = genera

        rows.append(row)
    return rows


def flag_columns():
    """The column names of flags.csv, in order."""
    columns = ["site", "date"] + GENERA + ["n_counted"]
    for label in THRESHOLDS:
        columns = columns + ["flag_" + label, "genera_" + label]
    return columns

def summary_rows(flags, sites):
    """One dictionary per site: how many dates have each flag, for each threshold."""
    rows = []
    for site in sites:
        # Only the rows of this site.
        site_flags = flags[flags["site"] == site]

        row = {"site": site, "n_dates": len(site_flags)}
        for label in THRESHOLDS:
            for flag in FLAG_NAMES:
                # == flag gives True/False for each date; sum() counts the Trues.
                row[flag + "_" + label] = int((site_flags["flag_" + label] == flag).sum())
        rows.append(row)
    return rows

# This block runs when you type "python retro.py".
if __name__ == "__main__":
    # Show wide tables on one line instead of wrapping them.
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)

    rows = []        # one inventory row per dataset that worked
    failed = []      # (dataset, reason) for each dataset that failed
    flag_list = []   # one dictionary per site x date, for flags.csv
    n_merged = 0     # how many rows disappeared by merging duplicate dates

    for dataset_id in DATASETS:
        print("Downloading", dataset_id, "...")
        try:
            raw = download(dataset_id)
            df, n_negative = clean(raw)
        except Exception as error:
            # Report the problem and continue with the next dataset.
            failed.append((dataset_id, str(error)))
            continue
        rows.append(inventory_row(dataset_id, df, n_negative))

        # Step 2: one row per date, then flag each date.
        merged = merge_duplicate_dates(df)
        n_merged = n_merged + (len(df) - len(merged))
        flag_list = flag_list + flag_rows(dataset_id, merged)

    inventory = pd.DataFrame(rows)

    print()
    print("Period:", START, "to", END, "(END not included), California dates")
    print("Weeks in the period (Monday-Sunday):", len(all_weeks()))
    print()

    print("INVENTORY")
    if len(inventory) > 0:
        print(inventory[["dataset", "first_date", "last_date", "n_samples",
                         "n_duplicate_dates", "n_weeks_without_sample", "n_negative"]].to_string(index=False))
        print()
        print("NaN COUNT PER GENUS (not counted)")
        nan_columns = ["nan_" + genus for genus in GENERA]
        print(inventory[["dataset"] + nan_columns].to_string(index=False))
    else:
        print("No dataset could be downloaded.")

    print()
    print("FAILED DATASETS:", len(failed))
    for dataset_id, reason in failed:
        print(" ", dataset_id, "->", reason)

    # ---------------------------------------------------------------
    # Step 2: flags.csv
    # ---------------------------------------------------------------
    # columns= keeps the column order (and works even if no rows were flagged).
    flags = pd.DataFrame(flag_list, columns=flag_columns())
    flags.to_csv(FLAGS_FILE, index=False)

    print()
    print("FLAGS")
    print(FLAGS_FILE, "written:", len(flags), "rows (site x date).",
          n_merged, "rows were merged into an existing date (duplicate dates).")
    print()
    for label in THRESHOLDS:
        print("flag_" + label + ":")
        print(flags["flag_" + label].value_counts().to_string())
        print()
    print("n_counted (how many of the 6 genera were counted):")
    print(flags["n_counted"].value_counts().sort_index().to_string())
    print()

        # The highest threshold is rare, so list every date that exceeds it.
    top_label = list(THRESHOLDS)[-1]
    top = flags[flags["flag_" + top_label] == "EXCEEDS"]
    print("Dates above", f"{THRESHOLDS[top_label]:,}", "cells/L:", len(top))
    if len(top) > 0:
        print(top[["site", "date", "genera_" + top_label]].to_string(index=False))

    # ---------------------------------------------------------------
    # Step 3: summary.csv
    # ---------------------------------------------------------------
    # The sites that downloaded correctly (failed datasets are left out).
    sites = [row["dataset"] for row in rows]
    summary = pd.DataFrame(summary_rows(flags, sites))
    summary.to_csv(SUMMARY_FILE, index=False)

    print()
    print("SUMMARY (number of dates per site)")
    print(SUMMARY_FILE, "written:", len(summary), "sites.")
    if len(summary) > 0:
        print(summary.to_string(index=False))
        print()
        # Check: the totals must match the FLAGS counts above.
        print("TOTAL")
        print(summary.drop(columns="site").sum().to_string())