import pandas as pd



steam_sales = [
    "2019-06-25", "2019-11-27", "2019-12-19",
    "2020-03-19", "2020-06-25", "2020-11-25", "2020-12-22",
    "2021-03-25", "2021-06-24", "2021-11-24", "2021-12-22",
    "2022-03-17", "2022-06-23", "2022-11-23", "2022-12-22",
    "2023-03-16", "2023-06-29", "2023-11-21", "2023-12-21",
    "2024-03-14", "2024-06-27", "2024-11-27", "2024-12-19",
    "2025-03-13", "2025-06-26", "2025-09-29", "2025-12-18",
    "2026-03-19", "2026-06-25", "2026-10-01",
]
steam_sale_dates = pd.to_datetime(steam_sales, utc=True)

def days_to_nearest_sale(date, sale_dates):
    diffs = abs(sale_dates - date)
    return diffs.min().total_seconds() / 86400
if __name__ == "__main__":
    df = pd.read_csv("sale_events.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values(["app_id", "timestamp"])
    df["gap"] = df.groupby("app_id")["timestamp"].diff()
    earliest = df["timestamp"].min() + pd.Timedelta(weeks=26)   
    latest = df["timestamp"].max() - pd.Timedelta(weeks=6)      
    cutoffs = pd.date_range(start=earliest, end=latest, freq="8W")

    all_rows = []

    for cutoff in cutoffs:
        train_data = df[df["timestamp"] < cutoff]
        label_end = cutoff + pd.Timedelta(weeks=2)
        bounded_sales = df[(df["timestamp"] >= cutoff) & (df["timestamp"] < label_end)]
        label_set = set(bounded_sales["app_id"].unique())

        features = train_data.groupby("app_id").agg(
            num_sales=("cut", "count"),
            avg_cut=("cut", "mean"),
            avg_gap_days=("gap", lambda x: x.mean().total_seconds() / 86400 if x.notna().any() else None),
            most_recent_sale=("timestamp", "max"),
            regular_price=("regular_price", "last")
        ).reset_index()

        features["days_since_last_sale"] = (cutoff - features["most_recent_sale"]).dt.total_seconds() / 86400
        features["label"] = features["app_id"].apply(lambda x: 1 if x in label_set else 0)
        features["days_to_nearest_sale"] = days_to_nearest_sale(cutoff, steam_sale_dates)
        features["cutoff_date"] = cutoff  # useful to keep, for a time-based split later

        features = features.dropna(subset=["avg_gap_days"])
        all_rows.append(features)

    final_features = pd.concat(all_rows, ignore_index=True)

    print(final_features.shape)
    print(final_features["label"].value_counts())

    final_features.to_csv("training_features.csv", index=False)

