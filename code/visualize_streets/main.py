import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np

def load_and_filter_data(file_path, street_name):
    """
    Load streets.csv and filter for the given street name.
    Returns a DataFrame with relevant data.
    """
    df = pd.read_csv(file_path)
    # Filter rows where Address contains the street name
    df_street = df[df['Address'].str.contains(street_name, case=False, na=False)].copy()
    # Assign Industry from Section
    df_street['Industry'] = df_street['Section']
    return df_street

def extract_address_number(address):
    """
    Extract numeric part of address, return None if non-numeric.
    """
    try:
        # Split address and take the last part as the number
        parts = address.split()
        num = int(parts[-1])
        return num
    except (ValueError, IndexError):
        return None

def detect_outliers(numbers):
    """
    Detect outliers using IQR method.
    Returns lower and upper bounds for valid numbers.
    """
    if not numbers:
        return 0, float("inf")
    Q1 = np.percentile(numbers, 25)
    Q3 = np.percentile(numbers, 75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return lower_bound, upper_bound

def create_visualization(df, street_name):
    """
    Create satellite view visualization for the given street.
    """
    # Assign colors to industries
    unique_industries = df['Industry'].unique()
    # Generate colors using a colormap for flexibility
    cmap = plt.get_cmap('tab20')
    industry_colors = {industry: cmap(i % 20) for i, industry in enumerate(unique_industries)}
    industry_colors['Unknown'] = 'white'  # White for unknown parcels

    # Extract numeric addresses for outlier detection
    address_numbers = []
    for addr in df['Address']:
        num = extract_address_number(addr)
        if num is not None:
            address_numbers.append(num)

    # Detect outliers
    lower_bound, upper_bound = detect_outliers(address_numbers)

    # Process addresses, excluding outliers
    odd_addresses = {}
    even_addresses = {}
    for _, row in df.iterrows():
        addr = row['Address']
        industry = row['Industry']
        num = extract_address_number(addr)
        if num is not None and lower_bound <= num <= upper_bound:
            if num % 2 == 0:
                even_addresses[num] = industry
            else:
                odd_addresses[num] = industry

    # Determine grid size based on valid addresses
    max_addr = max(
        max(odd_addresses.keys(), default=100),
        max(even_addresses.keys(), default=100)
    ) + 10
    grid_width = max_addr // 2 + 1  # Approximate number of slots needed per row

    # Create 2D grid
    odd_grid = ["Unknown"] * grid_width
    even_grid = ["Unknown"] * grid_width

    # Map addresses to grid positions
    for addr, industry in odd_addresses.items():
        pos = addr // 2
        if pos < grid_width:
            odd_grid[pos] = industry

    for addr, industry in even_addresses.items():
        pos = addr // 2
        if pos < grid_width:
            even_grid[pos] = industry

    # Plotting
    fig, ax = plt.subplots(figsize=(20, 4))

    # Draw odd addresses (top row)
    for i, industry in enumerate(odd_grid):
        color = industry_colors.get(industry, 'white')
        rect = patches.Rectangle((i, 1), 1, 1, facecolor=color, edgecolor="black")
        ax.add_patch(rect)
        # Label address
        addr = i * 2 + 1
        if industry != "Unknown" and addr in odd_addresses:
            ax.text(i + 0.5, 1.5, str(addr), ha="center", va="center", fontsize=8)

    # Draw even addresses (bottom row)
    for i, industry in enumerate(even_grid):
        color = industry_colors.get(industry, 'white')
        rect = patches.Rectangle((i, -1), 1, 1, facecolor=color, edgecolor="black")
        ax.add_patch(rect)
        # Label address
        addr = i * 2 + 2
        if industry != "Unknown" and addr in even_addresses:
            ax.text(i + 0.5, -0.5, str(addr), ha="center", va="center", fontsize=8)

    # Draw street (gray rectangle)
    street = patches.Rectangle((0, -0.2), grid_width, 0.4, facecolor="lightgray")
    ax.add_patch(street)

    # Set limits and labels
    ax.set_xlim(0, grid_width)
    ax.set_ylim(-2, 3)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel(f"{street_name} Street")
    ax.set_title(f"Abstract Satellite View of {street_name} Street (Odd vs Even Addresses, Outliers Excluded)")

    # Create legend
    legend_patches = [patches.Patch(color=color, label=industry) for industry, color in industry_colors.items()]
    plt.legend(handles=legend_patches, bbox_to_anchor=(1.05, 1), loc="upper left", borderaxespad=0.)

    plt.tight_layout()
    plt.show()

def main():
    # Input street name
    street_name = input("Enter the street name (e.g., Sienkiewicza): ").strip()
    file_path = "streets.csv"  # Path to the CSV file
    try:
        df = load_and_filter_data(file_path, street_name)
        if df.empty:
            print(f"No data found for street: {street_name}")
        else:
            create_visualization(df, street_name)
    except FileNotFoundError:
        print(f"Error: {file_path} not found")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
