import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib

final_features = pd.read_csv("training_features.csv", parse_dates=["cutoff_date"])

split_point = final_features["cutoff_date"].quantile(0.8)
train = final_features[final_features["cutoff_date"] <= split_point]
test = final_features[final_features["cutoff_date"] > split_point]

feature_cols = ["num_sales", "avg_cut", "avg_gap_days", "regular_price",
                "days_since_last_sale", "days_to_nearest_sale"]

x_train, y_train = train[feature_cols], train["label"]
x_test, y_test = test[feature_cols], test["label"]

# --- Logistic Regression baseline ---
lr_model = LogisticRegression(class_weight="balanced")
lr_model.fit(x_train, y_train)
lr_preds = lr_model.predict(x_test)
print("--- Logistic Regression ---")
print("Accuracy:", accuracy_score(y_test, lr_preds))
print("Precision:", precision_score(y_test, lr_preds))
print("Recall:", recall_score(y_test, lr_preds))
print("F1:", f1_score(y_test, lr_preds))

# --- Random Forest baseline ---
rf_model = RandomForestClassifier(class_weight="balanced", random_state=42)
rf_model.fit(x_train, y_train)
rf_preds = rf_model.predict(x_test)
print("--- Random Forest (baseline) ---")
print("Accuracy:", accuracy_score(y_test, rf_preds))
print("Precision:", precision_score(y_test, rf_preds))
print("Recall:", recall_score(y_test, rf_preds))
print("F1:", f1_score(y_test, rf_preds))

# --- Random Forest, hyperparameter-tuned ---
param_grid = {
    "n_estimators": [100, 200, 300],
    "max_depth": [None, 10, 20],
    "min_samples_split": [2, 5, 10]
}

grid = GridSearchCV(
    RandomForestClassifier(class_weight="balanced", random_state=42),
    param_grid,
    cv=3,
    scoring="f1",
    n_jobs=-1
)
grid.fit(x_train, y_train)

print("--- Random Forest (tuned) ---")
print("Best params:", grid.best_params_)
print("Best CV F1:", grid.best_score_)

best_model = grid.best_estimator_
best_preds = best_model.predict(x_test)
print("Test Accuracy:", accuracy_score(y_test, best_preds))
print("Test Precision:", precision_score(y_test, best_preds))
print("Test Recall:", recall_score(y_test, best_preds))
print("Test F1:", f1_score(y_test, best_preds))

# --- Save the best-performing model ---
joblib.dump(best_model, "sale_prediction_model.joblib")