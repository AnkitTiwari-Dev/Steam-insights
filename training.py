import pandas as pd

df = pd.read_csv("sale_events.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"],utc=True)

grouped = df.groupby("app_id")
event_counts = grouped.size()

df = df.sort_values(["app_id","timestamp"])
df["gap"] = df.groupby("app_id")["timestamp"].diff()
cutoff = df["timestamp"].max() - pd.Timedelta(weeks=7)
train_data = df[df["timestamp"] < cutoff]
label_end = cutoff + pd.Timedelta(weeks=2)
bounded_sales = df[(df["timestamp"] >= cutoff) & (df["timestamp"] < label_end)]
training_set = set(bounded_sales["app_id"].unique())

features = train_data.groupby("app_id").agg(
    num_sales=("cut","count"),
    avg_cut=("cut","mean"),
    avg_gap_days=("gap",lambda x: x.mean().total_seconds() / 86400 if x.notna().any() else None),
    most_recent_sale=("timestamp","max"),
    regular_price=("regular_price","last")
).reset_index()

features["days_since_last_sale"] = (cutoff - features["most_recent_sale"]).dt.total_seconds() / 86400
features["label"] = features["app_id"].apply(lambda x: 1 if x in training_set else 0)
features = features.dropna(subset=["avg_gap_days"])

print(features.shape)
print(features.head())
print(features["label"].value_counts())
features.to_csv("training_features.csv", index=False)