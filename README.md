# MDHAB analysis (2020–2024)

Analysis of marine dinoflagellate HAB (MDHAB) data from the CalHABMAP sites, using data from the SCCOOS ERDDAP server.

## Folders

- `scripps_dashboard/`: Streamlit dashboard for *Lingulodinium polyedra* at Scripps Pier (`data.py`, `app.py`, `requirements.txt`). It downloads fresh data every time the page opens.
- `retro_2020_2024/`: retrospective study of the 17 CalHABMAP "HABs" datasets, 2020–2024. `retro.py` downloads the data and flags exceedances of 10⁴ and 10⁶ cells/L for 6 MDHAB genera. `buscar.py` searches `flags.csv` by site, threshold, genus and date.

## Output files (in `retro_2020_2024/`)

- `inventory.csv`: one row per dataset: first and last date, number of samples, duplicate dates, weeks without a sample, negative values, and missing values per genus.
- `flags.csv`: one row per site and sample date: the 6 genus values (cells/L), `n_counted`, and for each threshold a flag and the genera that exceeded it.
- `summary.csv`: one row per site: number of dates in each flag category for each threshold.

## Flags

For each site and date, and for each threshold separately:

- **MISSING**: none of the 6 genera has a value.
- **EXCEEDS**: at least one counted genus is above the threshold (strictly greater). `genera_1e4` / `genera_1e6` list which ones, separated by `;`.
- **NO_EXCEEDANCE**: at least one genus was counted and none is above the threshold.

`genera_1e4` and `genera_1e6` are blank unless the flag for that threshold is EXCEEDS. `n_counted` shows how many of the 6 genera were counted (0–6).

## Data handling

- Blank = not counted (NaN). 0 = counted, none found. The two are never mixed.
- Negative values are treated as missing (NaN).
- Dates are California local dates (America/Los_Angeles).
- If a site has more than one sample on the same date, the highest value of each genus is kept.
- Weeks with no sample at all have no row in `flags.csv`. They are counted in `inventory.csv`.

## How to run

```
pip install -r scripps_dashboard/requirements.txt

cd retro_2020_2024
python retro.py
cd ..

cd scripps_dashboard
streamlit run app.py
```

`retro.py` writes its CSV files in the folder it is run from.

## Notes

- Data source: SCCOOS ERDDAP, https://erddap.sccoos.org/erddap/tabledap/index.html
- `Cochlodinium_spp` is the ERDDAP column name. Some sources use the newer name *Margalefidinium*.
- `Other_Dinoflagellates`, `Prorocentrum_spp` and `Ceratium_spp` group several species, so an exceedance in those columns refers to a group, not a single species.
