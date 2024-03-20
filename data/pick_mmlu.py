import argparse
import pandas as pd
import os
import random

from pathlib import Path

def process_files(input_folder, output_folder, k=20):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    for filename in os.listdir(input_folder):
        if filename.endswith('.csv'):
            df = pd.read_csv(os.path.join(input_folder, filename))
            df_sample = df.sample(n=k)
            #output_filename = os.path.splitext(filename)[0] + f'.{k}.csv'
            output_filename = f'{Path(filename).stem}.{k}.csv'
            df_sample.to_csv(os.path.join(output_folder, output_filename), index=False)
            

if __name__ == "__main__":
    random.seed(12400)
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", help="Input folder containing the CSV files")
    parser.add_argument("--output", "-o", help="Output folder to save the sampled CSV files")
    parser.add_argument("--k", "-k", help="Number of entries to sample from each CSV file", default=20, type=int)
    args = parser.parse_args()

    process_files(args.input, args.output, args.k)
