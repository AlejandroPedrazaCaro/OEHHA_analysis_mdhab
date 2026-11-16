# data.py
# Downloads the Scripps Pier HAB data from ERDDAP and prepares it for the dashboard.

import pandas as pd

# ---------------------------------------------------------------
# Settings (change these numbers here, nowhere else)
# ---------------------------------------------------------------
DATASET_ID = "HABs-ScrippsPier"
THRESHOLD_PERCENTILE = 95   # change this one number to move the threshold
YEARS = 5                   # length of the window, counted back from the latest sample

# Address of the CSV file on the ERDDAP server.
# After the "?" we list the three columns we want, separated by commas.
URL = (
    "https://erddap.sccoos.org/erddap/tabledap/"
    + DATASET_ID
    + ".csv?time,Lingulodinium_polyedra,Temp"
)


def load_data():
    """Download the full record and return it as a table (a pandas DataFrame)."""

    # Read the CSV straight from the web address.
    # ERDDAP puts the units (e.g. "UTC", "cells/L") on line 2 of the file,
    # so skiprows=[1] skips that line (Python counts lines from 0).
    df = pd.read_csv(URL, skiprows=[1])

    # The "time" column arrives as text like "2008-06-30T00:00:00Z".
    # Turn it into real dates so we can sort them and do date arithmetic.
    df["time"] = pd.to_datetime(df["time"])

    # Turn the two value columns into numbers.
    # errors="coerce" means: anything that is not a number becomes NaN.
    # NaN = "not counted". A real 0 stays 0 = "counted, none found".
    df["Lingulodinium_polyedra"] = pd.to_numeric(df["Lingulodinium_polyedra"], errors="coerce")
    df["Temp"] = pd.to_numeric(df["Temp"], errors="coerce")

    # Put the rows in date order, oldest first.
    df = df.sort_values("time")

    return df


def last_five_years(df):
    """Keep only the rows from the YEARS years before the latest sample."""

    # The newest date in the data. This moves forward by itself
    # when new samples are added to ERDDAP.
    latest = df["time"].max()

    # Go back YEARS years from that date, e.g. 2026-10-05 -> 2021-10-05.
    start = latest - pd.DateOffset(years=YEARS)

    # Keep the rows on or after the start date.
    # .copy() makes a separate table, so adding columns later
    # does not change (or warn about) the original one.
    recent = df[df["time"] >= start].copy()

    return recent


def compute_threshold(df):
    """Return two things: the threshold, and True/False for whether we had to use the fallback."""

    # Only counted samples. dropna() removes the NaN rows ("not counted").
    # Zeros stay in, because 0 is a real measurement.
    counts = df["Lingulodinium_polyedra"].dropna()

    # The percentile. quantile() wants a fraction, so 95 becomes 0.95.
    threshold = counts.quantile(THRESHOLD_PERCENTILE / 100)
    used_fallback = False

    # If so many samples are 0 that the percentile is 0, every non-zero
    # count would be flagged. In that case, use only samples with cells > 0.
    if threshold == 0:
        positive_counts = counts[counts > 0]
        threshold = positive_counts.quantile(THRESHOLD_PERCENTILE / 100)
        used_fallback = True

    return threshold, used_fallback


def flag_exceedances(df, threshold):
    """Add a True/False column "exceeds": True when the count is above the threshold."""

    df = df.copy()

    # Compare every count with the threshold, all rows at once.
    # A NaN count gives False, so "not counted" is never flagged.
    df["exceeds"] = df["Lingulodinium_polyedra"] > threshold

    return df


# This block runs only when you type "python data.py".
# It does NOT run when app.py imports this file.
# We use it to check each step by printing the results.
if __name__ == "__main__":
    df = load_data()
    print("Full record:", len(df), "rows, latest sample", df["time"].max())
    print()

    recent = last_five_years(df)
    print("5-year window:", recent["time"].min(), "to", recent["time"].max())
    print("Rows in window:", len(recent))
    print("  counted:", recent["Lingulodinium_polyedra"].notna().sum())
    print("  not counted (NaN):", recent["Lingulodinium_polyedra"].isna().sum())
    print("  exactly 0:", (recent["Lingulodinium_polyedra"] == 0).sum())
    print()

    threshold, used_fallback = compute_threshold(recent)
    print("Threshold (", THRESHOLD_PERCENTILE, "th percentile):", threshold, "cells/L")
    print("Used fallback (only samples > 0):", used_fallback)
    print()

    flagged = flag_exceedances(recent, threshold)
    exceedances = flagged[flagged["exceeds"]]
    print("Exceedances:", len(exceedances))
    print(exceedances)