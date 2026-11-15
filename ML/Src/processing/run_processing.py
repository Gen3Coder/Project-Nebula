"""Runs the whole processing chain in order: clean -> merge -> labels -> features.

Run:  python ML\\Src\\processing\\run_processing.py
"""
import clean_data
import merge_daily
import create_labels
import build_features

STEPS = [("1. Clean raw data", clean_data.main),
         ("2. Merge into daily / seasonal / yearly tables", merge_daily.main),
         ("3. Create onset events and labels", create_labels.main),
         ("4. Build features and training dataset", build_features.main)]

if __name__ == "__main__":
    for title, step in STEPS:
        print("\n" + "=" * 70 + f"\n {title}\n" + "=" * 70)
        step()
    print("\nProcessing finished. Training data: Data/Processed/training_dataset.csv")
