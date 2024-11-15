import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from collections import defaultdict

# Create DataFrame
data = '''Business Name,Owner,Address
Hotel Bristol,Szojchet E.,Warszawska 28
Hotel Gdański,Straxer M.,Kolejowa 80
Hotel Metropol,Weinsztejn Ch.,Kolejowa 77
Hotel Palace,Z. Baraniuk,Warszawska 16
Hotel Polonia,Berska P.,Lucka 135
Hotel Versal,Glejzer I.,Mickiewicza 4
Hotel Warszawski,Gulisz N.,Kolejowa 84
Hotel Pasaż,Fuks I.,Kolejowa 88'''

# Convert string data to DataFrame
df = pd.read_csv(pd.StringIO(data))

# Extract street names and numbers
df['Street'] = df['Address'].apply(lambda x: x.split()[0])
df['Number'] = df['Address'].apply(lambda x: int(x.split()[1]))

# Create a beautiful visualization
plt.figure(figsize=(12, 8))
plt.style.use('seaborn')

# Create a map of streets to y-positions
unique_streets = df['Street'].unique()
street_positions = {street: i for i, street in enumerate(unique_streets)}

# Dictionary to store x-offset for each street to prevent overlap
street_offsets = defaultdict(int)

# Plot points
for idx, row in df.iterrows():
    street = row['Street']
    number = row['Number']
    
    # Calculate position
    x = number
    y = street_positions[street]
    
    # Add small random offset to y to prevent perfect alignment
    y_offset = street_offsets[street] * 0.2
    street_offsets[street] += 1
    
    # Plot point
    plt.scatter(x, y + y_offset, s=100, alpha=0.6, c='darkblue')
    
    # Add business name label
    plt.annotate(row['Business Name'], 
                (x, y + y_offset),
                xytext=(5, 5),
                textcoords='offset points',
                fontsize=8,
                alpha=0.8)

# Customize the plot
plt.yticks(list(street_positions.values()), list(street_positions.keys()))
plt.xlabel('Street Number')
plt.title('Businesses in Kowel by Location', pad=20, fontsize=14)

# Add grid for better readability
plt.grid(True, linestyle='--', alpha=0.3)

# Adjust layout
plt.tight_layout()

# Show the plot
plt.show()