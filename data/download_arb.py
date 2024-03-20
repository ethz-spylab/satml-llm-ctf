#%%
# We download the Law portion of the ARB dataset, and package it as MMLU
import requests
response = requests.get("https://advanced-reasoning-benchmark.netlify.app/api/lib/law/")
data = response.json()

"""
Schema for each problem:
{
  "_id": "string",
  "Problem Statement": "string",
  "Problem Number": "string",
  "Answer Candidates": [
    "string",
    "string",
    "string",
    "string"
  ],
  "Final Answer": "A | B | C | D",
  "Problem Type": "string"
}
"""

#%%
print(len(data))
data[200]

#%%
# Filter out all that don't have 4 answer candidates
data = [d for d in data if len(d['Answer Candidates']) == 4]
print(len(data))
data[200]

#%%
import csv

def write_to_csv(file_name, data_list):
    with open(file_name, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # writer.writerow(['task', 'A', 'B', 'C', 'D', 'Final Answer'])  # Header is commented out
        for j, data in enumerate(data_list):
            print(f"Writing row {j}")
            print(data['Answer Candidates'])
            csv_row = [
                data['Problem Statement'],
                data['Answer Candidates'][0],
                data['Answer Candidates'][1],
                data['Answer Candidates'][2],
                data['Answer Candidates'][3],
                data['Final Answer']
            ]
            writer.writerow(csv_row)

#%%
# Make 10 files with 20 questions each
N_FILES = 10
from pathlib import Path
OUTPUT_DIR = Path("small_data/arb_law")

if not OUTPUT_DIR.exists():
    OUTPUT_DIR.mkdir(parents=True)


import random
random.seed(654321)
random.shuffle(data)

for i in range(N_FILES):
    print(f"Writing file {i}")
    file_name = OUTPUT_DIR / f"arb_law_{i}.20.csv"
    write_to_csv(file_name, data[i*20:(i+1)*20])


# %%
