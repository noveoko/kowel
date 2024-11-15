import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

# Create a new graph
G = nx.Graph()

# Known coordinates (converted from degrees to relative positions)
coords = {
    'Kościelna': (51.21603, 24.69836),
    'Monopolowa': (51.20480, 24.70139),
    'Więzienna': (51.20984, 24.70038),
    'Budyszczańska': (51.20415, 24.70588),
    'FABRYCZNA': (51.21120, 24.71221),
    'BUDOWLANA': (51.20995, 24.71463),
    'LISTOPADOWA': (51.21638, 24.71229),
    'Królowej Bony': (51.21698, 24.70651),
    'Pereca': (51.21565, 24.71263),
    'Kolejowa': (51.21782, 24.71034),
    'Szewczenki': (51.21773, 24.70255),
    'Mickiewicza': (51.21134, 24.70593),
    '3-go Maja': (51.21273, 24.70890),
    'Szpitalna': (51.20808, 24.72311),
    'Pasieczna': (51.20538, 24.72574),
    'Zaułek Kolejowy': (51.20282, 24.73368),
    'Południowa': (51.20505, 24.72890),
    'Bielińska': (51.22125, 24.72687),
    'Powurska': (51.21803, 24.73365)
}

# Normalize coordinates to 0-1 range for better visualization
min_lat = min(lat for lat, _ in coords.values())
max_lat = max(lat for lat, _ in coords.values())
min_lon = min(lon for _, lon in coords.values())
max_lon = max(lon for _, lon in coords.values())

pos = {street: ((lon - min_lon)/(max_lon - min_lon), (lat - min_lat)/(max_lat - min_lat)) 
       for street, (lat, lon) in coords.items()}

# Add all streets as nodes
all_streets = [
    # District 1
    'Górka', 'Marszałka Śmigłego Rydza', 'Apteczna', 'Szuhajskiego', 'Kościelna', 
    'Strażacka', 'Soborna',
    
    # District 2
    'Maciejowska', 'Wola', 'Szlachecka', 'Długa', 'Chmielna', 'Lubliniecka',
    'Mało Gonczarna', 'Dużo Gonczarna', 'Ogrodowa', 'Nadbrzeżna', 'Cerkiewna', 'Gospodarcza',
    
    # District 3
    'Krótka', 'Handlowa', 'Mieszczańska', 'Kąpielowa', 'Włodzimierska', 'Rzeczna', 'Szkolna',
    
    # District 4
    'Magistracka', 'Legionów', 'Monopolowa', 'Więzienna', 'Jasna', 'Budyszczańska',
    'Kowalska', 'Cicha', 'Staro Cmentarna',
    
    # District 5
    'Królowej Bony', 'Żwirki', 'Wigury', 'Staszyca', '50 P. P, Strzel. Kres.',
    'Wilcza', 'Pereca', 'Kolejowa', 'Listopadowa', 'Szewczenki',
    
    # District 6
    'Sulkiewicza', 'Krzywa', 'Żeromskiego', 'Poniatowskiego', 'Hołówki',
    'Strzelecka', 'Sienkiewicza', 'Daszyńskiego', 'Pograniczna', 'Mościckiego', 'Tuszowskiego',
    
    # District 7
    'Kościuszki', 'Mickiewicza', 'Ciasna', 'Filarecka', 'Cyrkowa', '3-go Maja',
    'Przeskok', 'ks. Bandurskiego', 'ks. Sznarbachowskiego', 'Piaskowa', 'Komorowska',
    'Rolna', 'al. Marszałka Piłsudskiego', '27 Dywizji Piechoty', 'Bezimienna', 'Pomnikowa',
    
    # District 8
    'Limanowskiego', 'Dzika', 'Niecała', 'Krucza', 'Wiejska', 'Wygonna',
    'Cmentarna', 'Szpitalna', 'Nowowiejska', 'Pasieczna', 'Gibalskiego', 'Podjaworska',
    'Spokojna', 'Hoża', 'Zaułek Kolejowy', 'Południowa',
    
    # District 9
    'Bielińska', 'Wspólna', 'Koszykowa', 'Myśliwska', 'Zgoda', 'Kresowa',
    'Żórawia', 'Gęsia', 'Krakowska', 'Nowy Świat', 'Kolodnicka', 'Mokra',
    'Zaułek Krótki', 'Dąbrowskiego', 'Północna', 'Nasypowa', 'Polna', 'Miodowa',
    'Poleska', 'Zielona',
    
    # District 10
    'Powurska', 'Lisa Kuli', 'Topolowa', 'Wierzbowa', 'Torowa', 'Brzozowa',
    'Szeroka', 'Narożna', 'Miła', 'Wąska', 'Jaworowa', 'Prosta', 'Obwodowa',
    'Okrzei', '1-go Maja', 'Waligórskiego', 'Wrzosowa', 'Wielka', 'Parkowa'
]

# Add all nodes
for street in all_streets:
    G.add_node(street)

# Add edges based on district groupings and likely connections
edges = [
    # District 1 (Central/Church area)
    ('Kościelna', 'Strażacka'), ('Strażacka', 'Soborna'),
    ('Soborna', 'Apteczna'), ('Apteczna', 'Szuhajskiego'),
    ('Górka', 'Marszałka Śmigłego Rydza'),
    
    # District 2 (Western area)
    ('Maciejowska', 'Wola'), ('Wola', 'Szlachecka'),
    ('Długa', 'Chmielna'), ('Chmielna', 'Lubliniecka'),
    ('Mało Gonczarna', 'Dużo Gonczarna'), ('Ogrodowa', 'Nadbrzeżna'),
    ('Nadbrzeżna', 'Cerkiewna'), ('Cerkiewna', 'Gospodarcza'),
    
    # District 3 (Market area)
    ('Krótka', 'Handlowa'), ('Handlowa', 'Mieszczańska'),
    ('Mieszczańska', 'Kąpielowa'), ('Kąpielowa', 'Włodzimierska'),
    ('Włodzimierska', 'Rzeczna'), ('Rzeczna', 'Szkolna'),
    
    # District 4 (Administrative center)
    ('Magistracka', 'Legionów'), ('Legionów', 'Monopolowa'),
    ('Monopolowa', 'Więzienna'), ('Więzienna', 'Jasna'),
    ('Jasna', 'Budyszczańska'), ('Budyszczańska', 'Kowalska'),
    ('Kowalska', 'Cicha'), ('Cicha', 'Staro Cmentarna'),
    
    # District 5 (Railway station area)
    ('Królowej Bony', 'Żwirki'), ('Żwirki', 'Wigury'),
    ('Wigury', 'Staszyca'), ('Staszyca', '50 P. P, Strzel. Kres.'),
    ('Wilcza', 'Pereca'), ('Pereca', 'Kolejowa'),
    ('Kolejowa', 'Listopadowa'), ('Listopadowa', 'Szewczenki'),
    
    # District 6 (Northern residential)
    ('Sulkiewicza', 'Krzywa'), ('Krzywa', 'Żeromskiego'),
    ('Żeromskiego', 'Poniatowskiego'), ('Poniatowskiego', 'Hołówki'),
    ('Strzelecka', 'Sienkiewicza'), ('Sienkiewicza', 'Daszyńskiego'),
    
    # District 7 (Central residential)
    ('Kościuszki', 'Mickiewicza'), ('Mickiewicza', '3-go Maja'),
    ('3-go Maja', 'Przeskok'), ('Przeskok', 'ks. Bandurskiego'),
    ('Piaskowa', 'Komorowska'), ('Komorowska', 'Rolna'),
    
    # District 8 (Eastern residential)
    ('Limanowskiego', 'Dzika'), ('Dzika', 'Niecała'),
    ('Niecała', 'Krucza'), ('Krucza', 'Wiejska'),
    ('Wiejska', 'Wygonna'), ('Wygonna', 'Cmentarna'),
    ('Cmentarna', 'Szpitalna'), ('Szpitalna', 'Nowowiejska'),
    
    # District 9 (Northeastern residential)
    ('Bielińska', 'Wspólna'), ('Wspólna', 'Koszykowa'),
    ('Koszykowa', 'Myśliwska'), ('Myśliwska', 'Zgoda'),
    ('Zgoda', 'Kresowa'), ('Kresowa', 'Żórawia'),
    
    # District 10 (Eastern industrial)
    ('Powurska', 'Lisa Kuli'), ('Lisa Kuli', 'Topolowa'),
    ('Topolowa', 'Wierzbowa'), ('Wierzbowa', 'Torowa'),
    ('Torowa', 'Brzozowa'), ('Brzozowa', 'Szeroka'),
    
    # Inter-district connections
    ('3-go Maja', 'FABRYCZNA'), ('FABRYCZNA', 'BUDOWLANA'),
    ('BUDOWLANA', 'LISTOPADOWA'), ('Kolejowa', 'Torowa'),
    ('Szpitalna', 'Pasieczna'), ('Pasieczna', 'Południowa'),
    ('Bielińska', 'Powurska'), ('Mickiewicza', 'Kościelna'),
    ('Monopolowa', 'Handlowa'), ('Szewczenki', 'Sulkiewicza'),
    ('Wiejska', 'Parkowa'), ('Parkowa', 'Powurska')
]

# Add edges to graph
G.add_edges_from(edges)

# Create position dictionary for unknown coordinates using spring layout
pos_spring = nx.spring_layout(G, pos=pos, fixed=list(coords.keys()), k=0.5, iterations=100)

# Plot the graph
plt.figure(figsize=(20, 20))

# Draw edges first
nx.draw_networkx_edges(G, pos_spring, edge_color='gray', alpha=0.5)

# Draw nodes
known_coords = list(coords.keys())
other_nodes = [n for n in G.nodes() if n not in known_coords]

nx.draw_networkx_nodes(G, pos_spring, 
                      nodelist=known_coords,
                      node_color='lightblue',
                      node_size=300,
                      node_shape='o')

nx.draw_networkx_nodes(G, pos_spring, 
                      nodelist=other_nodes,
                      node_color='lightgray',
                      node_size=300,
                      node_shape='o')

# Draw labels
nx.draw_networkx_labels(G, pos_spring, font_size=6)

plt.title("Complete Street Network of Kowel (1939)")
plt.axis('off')
plt.tight_layout()