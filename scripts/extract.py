import os
import requests
import pandas as pd

RAW_DATA_DIR = "data/raw"

def ensure_directories():
  """Creates a data/raw folder if it doesn't exist."""
  os.makedirs(RAW_DATA_DIR, exist_ok=True)

def download_parquet(url, filename):
  """Downloads a parquet file from the given URL and saves it to the data/raw folder."""
  ensure_directories()
  save_path = os.path.join(RAW_DATA_DIR, filename)

  print(f"\nDownloading parquet from {url}...")

  response = requests.get(url)
  if response.status_code == 200:
    with open(save_path, "wb") as f:
      f.write(response.content)
    print(f"Successfully saved to {save_path}")
    return save_path
  else:
    print(f"Failed to downliad. Status code: {response.status_code}")
    return None

def download_csv(url, filename):
  """Downloads a CVS file from the given URL and saves it to the data/raw folder."""
  ensure_directories()
  save_path = os.path.join(RAW_DATA_DIR, filename)

  print(f"\nDownloading CSV from {url}...")

  df = pd.read_csv(url)
  df.to_csv(save_path, index=False)

  print(f"Successfully saved to {save_path}\n")
  return save_path

if __name__ == "__main__":
  csv_url = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
  parquet_url = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-09.parquet"

  download_parquet(parquet_url, "yellow_tripdata_2026-09.parquet")
  download_csv(csv_url, "taxi_zone_lookup.csv")