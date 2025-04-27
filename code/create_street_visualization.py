import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
from collections import defaultdict

# Data (parsed from provided text)
data = [
    {"Business Name": "Hotel Gdański", "Owner": "Straxer M.", "Address": "Kolejowa 80", "Industry": "Hotel"},
    {"Business Name": "Hotel Metropol", "Owner": "Weinsztejn Ch.", "Address": "Kolejowa 77", "Industry": "Hotel"},
    {"Business Name": "Hotel Warszawski", "Owner": "Gulisz N.", "Address": "Kolejowa 84", "Industry": "Hotel"},
    {"Business Name": "Hotel Pasaż", "Owner": "Fuks I.", "Address": "Kolejowa 88", "Industry": "Hotel"},
    {"Business Name": "Sheet metal workers", "Owner": "Fajnland Sz.", "Address": "Kolejowa", "Industry": "Sheet Metal"},
    {"Business Name": "Gunsmiths", "Owner": "Gliniecki i Kowalski", "Address": "Kolejowa 53", "Industry": "Gunsmith"},
    {"Business Name": "Doctor", "Owner": "Ciechnowicz Michał", "Address": "Kolejowa 26", "Industry": "Medical"},
    {"Business Name": "Doctor", "Owner": "Królewski Wacław (laryngology)", "Address": "Kolejowa 90", "Industry": "Medical"},
    {"Business Name": "Doctor", "Owner": "Leble Zygmunt (internal)", "Address": "Kolejowa 90", "Industry": "Medical"},
    {"Business Name": "Confectionery", "Owner": "Czwanczara B.", "Address": "Kolejowa 4", "Industry": "Confectionery"},
    {"Business Name": "Confectionery", "Owner": "Głouszek W.", "Address": "Kolejowa 63", "Industry": "Confectionery"},
    {"Business Name": "Cap Makers", "Owner": "Elfantel M.", "Address": "Kolejowa 5", "Industry": "Cap Making"},
    {"Business Name": "Cap Makers", "Owner": "Glwire D.", "Address": "Kolejowa 48", "Industry": "Cap Making"},
    {"Business Name": "Wood", "Owner": "Furszteler Ch.", "Address": "Kolejowa 5", "Industry": "Wood"},
    {"Business Name": "Hairdressers", "Owner": "Fajner L.", "Address": "Kolejowa 79", "Industry": "Hairdressing"},
    {"Business Name": "Hairdressers", "Owner": "Fiszek Szl.", "Address": "Kolejowa 1", "Industry": "Hairdressing"},
    {"Business Name": "Hairdressers", "Owner": "Satrykman M.", "Address": "Kolejowa 64", "Industry": "Hairdressing"},
    {"Business Name": "Hairdressers", "Owner": "Strużer J.", "Address": "Kolejowa 85", "Industry": "Hairdressing"},
    {"Business Name": "Hairdressers", "Owner": "Sztojn Ch.", "Address": "Kolejowa 33", "Industry": "Hairdressing"},
    {"Business Name": "Hairdressers", "Owner": "Loi i Kerzner", "Address": "Kolejowa 91", "Industry": "Hairdressing"},
    {"Business Name": "Haberdashery", "Owner": "Fajner Ch.", "Address": "Kolejowa 79", "Industry": "Haberdashery"},
    {"Business Name": "Haberdashery", "Owner": "Kagan J.", "Address": "Kolejowa 11", "Industry": "Haberdashery"},
    {"Business Name": "Haberdashery", "Owner": "Poliszuk M.", "Address": "Kolejowa 2", "Industry": "Haberdashery"},
    {"Business Name": "Haberdashery", "Owner": "Wajnsztojn M.", "Address": "Kolejowa", "Industry": "Haberdashery"},
    {"Business Name": "Tea Houses", "Owner": "Cytryn", "Address": "Kolejowa 21", "Industry": "Tea House"},
    {"Business Name": "Tea Houses", "Owner": "Szylter A.", "Address": "Kolejowa 86", "Industry": "Tea House"},
    {"Business Name": "Bookbinders", "Owner": "Wydra F.", "Address": "Kolejowa 8", "Industry": "Bookbinding"},
    {"Business Name": "Restaurants", "Owner": "Popis", "Address": "Kolejowa 59", "Industry": "Restaurant"},
    {"Business Name": "Shoe Upper Makers", "Owner": "Has A.", "Address": "Kolejowa 16", "Industry": "Shoe Making"},
    {"Business Name": "Cafe", "Owner": "Awruch B.", "Address": "Kolejowa 87", "Industry": "Cafe"},
    {"Business Name": "Cafe", "Owner": "Bor G.", "Address": "Kolejowa 74", "Industry": "Cafe"},
    {"Business Name": "Cafe", "Owner": "Gibel B.", "Address": "Kolejowa 1", "Industry": "Cafe"},
    {"Business Name": "Cafe", "Owner": "Hrzyb St.", "Address": "Kolejowa 83", "Industry": "Cafe"},
    {"Business Name": "Cafe", "Owner": "Lusiak N.", "Address": "Kolejowa 48", "Industry": "Cafe"},
    {"Business Name": "Cafe", "Owner": "Puchalska E.", "Address": "Kolejowa 82", "Industry": "Cafe"},
    {"Business Name": "Cafe", "Owner": "Zigmundt Ch.", "Address": "Kolejowa 85", "Industry": "Cafe"},
    {"Business Name": "Cafe", "Owner": "Kabaszczuk", "Address": "Kolejowa 71", "Industry": "Cafe"},
    {"Business Name": "Bathing Facilities", "Owner": "Fuks J. and Ska", "Address": "Kolejowa 17", "Industry": "Bathing"},
    {"Business Name": "Colonial Articles", "Owner": "Bucher J.", "Address": "Kolejowa 21", "Industry": "Colonial Articles"},
    {"Business Name": "Colonial Articles", "Owner": "Figel Z.", "Address": "Kolejowa 2", "Industry": "Colonial Articles"},
    {"Business Name": "Colonial Articles", "Owner": "Fisz L.", "Address": "Kolejowa 2", "Industry": "Colonial Articles"},
    {"Business Name": "Blacksmiths", "Owner": "Boker S.", "Address": "Kolejowa 25", "Industry": "Blacksmith"},
    {"Business Name": "Tailors", "Owner": "Goldhaner Sz.", "Address": "Kolejowa 10", "Industry": "Tailoring"},
    {"Business Name": "Tailors", "Owner": "Jankowski J.", "Address": "Kolejowa 13", "Industry": "Tailoring"},
    {"Business Name": "Tailors", "Owner": "Rochman J.", "Address": "Kolejowa 50", "Industry": "Tailoring"},
    {"Business Name": "Tailors", "Owner": "Wojborszpil A.", "Address": "Kolejowa 13", "Industry": "Tailoring"},
    {"Business Name": "Bookstores", "Owner": "Bachowiec M.", "Address": "Kolejowa 88", "Industry": "Bookstore"},
    {"Business Name": "Bookstores", "Owner": "Kultura", "Address": "Kolejowa 2", "Industry": "Bookstore"},
    {"Business Name": "Bookstores", "Owner": "Plat M. i Szwarcblat M.", "Address": "Kolejowa 2", "Industry": "Bookstore"},
    {"Business Name": "Bookstores", "Owner": "Światło", "Address": "Kolejowa 88", "Industry": "Bookstore"},
    {"Business Name": "Textiles", "Owner": "Kuzniec", "Address": "Kolejowa 33", "Industry": "Textiles"},
    {"Business Name": "Ship Offices Chargeurs Réunis T. A.", "Owner": "", "Address": "Kolejowa 58", "Industry": "Shipping"},
    {"Business Name": "Ship Offices Cosulich Line", "Owner": "", "Address": "Kolejowa 35", "Industry": "Shipping"},
    {"Business Name": "Ship Offices Królewsko Dutche Lloyd", "Owner": "", "Address": "Kolejowa 88", "Industry": "Shipping"},
    {"Business Name": "Ship Offices Red Star Line", "Owner": "", "Address": "Kolejowa 91", "Industry": "Shipping"},
    {"Business Name": "Ship Offices Scandinavian-American Line", "Owner": "", "Address": "Kolejowa 43", "Industry": "Shipping"},
    {"Business Name": "Ship Offices The Royal Mail Steam Packet Company", "Owner": "", "Address": "Nowokolejowa 3", "Industry": "Shipping"},
    {"Business Name": "Ship Offices White Star Line", "Owner": "", "Address": "Kolejowa 91", "Industry": "Shipping"},
    {"Business Name": "Ship Offices Bałtycko-Amerykańska Linja", "Owner": "", "Address": "Kolejowa 65", "Industry": "Shipping"},
    {"Business Name": "Stationery", "Owner": "Aszkienazy Ch.", "Address": "Kolejowa 63", "Industry": "Stationery"},
    {"Business Name": "Beer Houses", "Owner": "Bober M.", "Address": "Kolejowa 2", "Industry": "Beer House"},
    {"Business Name": "Beer Houses", "Owner": "Raby R.", "Address": "Kolejowa 4", "Industry": "Beer House"},
    {"Business Name": "Beer Houses", "Owner": "Sochaczowski J.", "Address": "Kolejowa 44", "Industry": "Beer House"},
    {"Business Name": "Beer Houses", "Owner": "Szojntop S.", "Address": "Kolejowa 2", "Industry": "Beer House"},
    {"Business Name": "Unknown", "Owner": "Zysblat T.", "Address": "Kolejowa 98", "Industry": "Unknown"},
    {"Business Name": "Unknown", "Owner": "Auchman E.", "Address": "Kolejowa 56", "Industry": "Unknown"},
    {"Business Name": "Unknown", "Owner": "Balicka M.", "Address": "Kolejowa 75", "Industry": "Unknown"},
    {"Business Name": "Railway Sleepers", "Owner": "Import, Two Przemysłowo-Handlowe", "Address": "Kolejowa 91", "Industry": "Railway"},
    {"Business Name": "Furnished Rooms", "Owner": "Messer D.", "Address": "Kolejowa 41", "Industry": "Furnished Rooms"},
    {"Business Name": "Furnished Rooms", "Owner": "Zejlik B.", "Address": "Kolejowa 88", "Industry": "Furnished Rooms"},
    {"Business Name": "Laundries", "Owner": "Sikora", "Address": "Kolejowa 52", "Industry": "Laundry"},
    {"Business Name": "Restaurants", "Owner": "Kazimierska J.", "Address": "Kolejowa 2", "Industry": "Restaurant"},
    {"Business Name": "Restaurants", "Owner": "Kotkiewicz J.", "Address": "Kolejowa 60", "Industry": "Restaurant"},
    {"Business Name": "Restaurants", "Owner": "Mazurkiewicz J.", "Address": "Kolejowa 43", "Industry": "Restaurant"},
    {"Business Name": "Butchers", "Owner": "Atlas E.", "Address": "Kolejowa 31", "Industry": "Butcher"},
    {"Business Name": "Butchers", "Owner": "Bater and Szyfman", "Address": "Kolejowa 12", "Industry": "Butcher"},
    {"Business Name": "Butchers", "Owner": "Egber S.", "Address": "Kolejowa 36", "Industry": "Butcher"},
    {"Business Name": "Butchers", "Owner": "Goryń J.", "Address": "Kolejowa 6", "Industry": "Butcher"},
    {"Business Name": "Butchers", "Owner": "Pietruszka J.", "Address": "Kolejowa 13", "Industry": "Butcher"},
    {"Business Name": "Butchers", "Owner": "Rojtblat", "Address": "Kolejowa 2", "Industry": "Butcher"},
    {"Business Name": "Leather", "Owner": "Byk B.", "Address": "Kolejowa 7", "Industry": "Leather"},
    {"Business Name": "Leather", "Owner": "Gonik M.", "Address": "Kolejowa 29", "Industry": "Leather"},
    {"Business Name": "Leather", "Owner": "Wolcsolbaum B.", "Address": "Kolejowa 20", "Industry": "Leather"},
    {"Business Name": "Leather", "Owner": "Zalchondlor U.", "Address": "Kolejowa 14", "Industry": "Leather"},
    {"Business Name": "Foodstuffs", "Owner": "Babicki J.", "Address": "Kolejowa 12", "Industry": "Foodstuffs"},
    {"Business Name": "Foodstuffs", "Owner": "Ber M.", "Address": "Kolejowa 74", "Industry": "Foodstuffs"},
    {"Business Name": "Foodstuffs", "Owner": "Byk Sz.", "Address": "Kolejowa 46", "Industry": "Foodstuffs"},
    {"Business Name": "Foodstuffs", "Owner": "Chanis M.", "Address": "Kolejowa 36", "Industry": "Foodstuffs"},
    {"Business Name": "Spirits", "Owner": "Grinblat I.", "Address": "Kolejowa 38", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Grynblat M.", "Address": "Kolejowa 38", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Kierżnor N.", "Address": "Kolejowa 67", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Rajz. L.", "Address": "Kolejowa 10", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Singał S.", "Address": "Kolejowa 76", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Szuf G.", "Address": "Kolejowa 58", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Tchor W.", "Address": "Kolejowa 87", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Tenenbojm", "Address": "Kolejowa 49", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Wajnsztejn Ch.", "Address": "Kolejowa 83", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Wirwer W.", "Address": "Kolejowa 87", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Zafran B.", "Address": "Kolejowa 24", "Industry": "Spirits"},
    {"Business Name": "Wells - Construction", "Owner": "Bronsztejn M.", "Address": "Kolejowa", "Industry": "Construction"},
    {"Business Name": "Shoemaker's Utensils", "Owner": "Fajgenbaum A.", "Address": "Kolejowa 16", "Industry": "Shoemaking"},
    {"Business Name": "Shoemakers", "Owner": "Berliński St.", "Address": "Kolejowa 83", "Industry": "Shoemaking"},
    {"Business Name": "Shoemakers", "Owner": "Glaz A.", "Address": "Kolejowa 2", "Industry": "Shoemaking"},
    {"Business Name": "Shoemakers", "Owner": "Press S.", "Address": "Kolejowa 23", "Industry": "Shoemaking"},
    {"Business Name": "Shoemakers", "Owner": "Rojtor B.", "Address": "Kolejowa 56", "Industry": "Shoemaking"},
    {"Business Name": "Shoemakers", "Owner": "Szmojaz M.", "Address": "Kolejowa 52", "Industry": "Shoemaking"},
    {"Business Name": "Spirits", "Owner": "", "Address": "Kolejowa 39", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Lejwi W.", "Address": "Kolejowa 54", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Lorner S.", "Address": "Kolejowa 39", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Lewi A.", "Address": "Kolejowa 5", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Lewi W.", "Address": "Kolejowa 54", "Industry": "Spirits"},
    {"Business Name": "Spirits", "Owner": "Porogal A.", "Address": "Kolejowa 24", "Industry": "Spirits"},
    {"Business Name": "Tobacco products", "Owner": "Klepacz Sz.", "Address": "Kolejowa 87", "Industry": "Tobacco"},
    {"Business Name": "Tobacco products", "Owner": "Labus Fr.", "Address": "Kolejowa 88", "Industry": "Tobacco"},
    {"Business Name": "Tobacco products", "Owner": "Mrówczyński W.", "Address": "Kolejowa 36", "Industry": "Tobacco"},
    {"Business Name": "Tobacco products", "Owner": "Sztojngardt B.", "Address": "Kolejowa 13", "Industry": "Tobacco"},
    {"Business Name": "Tobacco products", "Owner": "Zurakowska Z.", "Address": "Kolejowa", "Industry": "Tobacco"},
    {"Business Name": "Cold cuts", "Owner": "Banczyk M.", "Address": "Kolejowa 3", "Industry": "Cold Cuts"},
    {"Business Name": "Vodka and liqueur factories", "Owner": "Pawlicha S.", "Address": "Kolejowa", "Industry": "Spirits"},
    {"Business Name": "Watchmakers", "Owner": "Chiżyk J.", "Address": "Kolejowa 87", "Industry": "Watchmaking"},
    {"Business Name": "Watchmakers", "Owner": "Engelsberg H.", "Address": "Kolejowa 37", "Industry": "Watchmaking"},
    {"Business Name": "Dentists", "Owner": "Korner J.", "Address": "Kolejowa 44", "Industry": "Medical"},
]

# Create DataFrame
df = pd.DataFrame(data)

# Assign colors to industries
industry_colors = {
    "Hotel": "red",
    "Sheet Metal": "gray",
    "Gunsmith": "black",
    "Medical": "blue",
    "Confectionery": "pink",
    "Cap Making": "purple",
    "Wood": "brown",
    "Hairdressing": "orange",
    "Haberdashery": "yellow",
    "Tea House": "green",
    "Bookbinding": "cyan",
    "Restaurant": "magenta",
    "Shoe Making": "darkblue",
    "Cafe": "lightgreen",
    "Bathing": "lightblue",
    "Colonial Articles": "darkgreen",
    "Blacksmith": "darkgray",
    "Tailoring": "violet",
    "Bookstore": "gold",
    "Textiles": "lime",
    "Shipping": "navy",
    "Stationery": "teal",
    "Beer House": "coral",
    "Unknown": "white",
    "Railway": "darkred",
    "Furnished Rooms": "lightgray",
    "Laundry": "lightcyan",
    "Butcher": "crimson",
    "Leather": "sienna",
    "Foodstuffs": "olive",
    "Spirits": "maroon",
    "Construction": "indigo",
    "Shoemaking": "darkcyan",
    "Tobacco": "salmon",
    "Cold Cuts": "plum",
    "Watchmaking": "silver"
}

# Process addresses
address_to_industry = {}
for _, row in df.iterrows():
    addr = row["Address"]
    industry = row["Industry"]
    # Extract number from address
    try:
        num = int(addr.split()[-1]) if addr != "Kolejowa" and addr.startswith("Kolejowa") else 1000
    except:
        num = 1000  # Default for non-numeric or missing addresses
    address_to_industry[num] = industry

# Create a grid (1D street)
max_addr = max([k for k in address_to_industry.keys() if k != 1000], default=100) + 10
grid_size = max_addr + 1
grid = ["Unknown"] * grid_size

for addr, industry in address_to_industry.items():
    if addr < grid_size:
        grid[addr] = industry
    else:
        # Place non-numeric addresses at the end
        for i in range(grid_size):
            if grid[i] == "Unknown":
                grid[i] = industry
                break

# Plotting
fig, ax = plt.subplots(figsize=(20, 2))
for i, industry in enumerate(grid):
    color = industry_colors.get(industry, "white")
    rect = patches.Rectangle((i, 0), 1, 1, facecolor=color, edgecolor="black")
    ax.add_patch(rect)

# Set limits and labels
ax.set_xlim(0, grid_size)
ax.set_ylim(0, 1)
ax.set_xticks(range(0, grid_size, 5))
ax.set_xticklabels([str(i) if i < 1000 else "N/A" for i in range(0, grid_size, 5)])
ax.set_yticks([])
ax.set_xlabel("Address on Kolejowa")
ax.set_title("Abstract Satellite View of Kolejowa Street")

# Create legend
legend_patches = [patches.Patch(color=color, label=industry) for industry, color in industry_colors.items()]
plt.legend(handles=legend_patches, bbox_to_anchor=(1.05, 1), loc="upper left", borderaxespad=0.)

plt.tight_layout()
plt.show()
