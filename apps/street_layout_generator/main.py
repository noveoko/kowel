import networkx as nx
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
import random
from collections import defaultdict

@dataclass
class Street:
    name: str
    lat: float = None
    lon: float = None
    connected_streets: List[str] = None
    
    def __post_init__(self):
        if self.connected_streets is None:
            self.connected_streets = []

class CityGraph:
    def __init__(self):
        self.graph = nx.Graph()
        self.streets: Dict[str, Street] = {}
        
    def add_street(self, street: Street):
        self.streets[street.name] = street
        self.graph.add_node(street.name, 
                           lat=street.lat, 
                           lon=street.lon)
        
    def connect_streets(self, street1: str, street2: str):
        if street1 in self.streets and street2 in self.streets:
            self.graph.add_edge(street1, street2)
            self.streets[street1].connected_streets.append(street2)
            self.streets[street2].connected_streets.append(street1)
            
    def get_connectivity_score(self) -> float:
        """Calculate connectivity score based on network metrics"""
        if len(self.graph) < 2:
            return 0.0
            
        metrics = {
            'avg_degree': np.mean([d for _, d in self.graph.degree()]),
            'clustering': nx.average_clustering(self.graph),
            'connectivity': nx.edge_connectivity(self.graph) if nx.is_connected(self.graph) else 0
        }
        
        return (metrics['avg_degree'] * 0.4 + 
                metrics['clustering'] * 0.3 + 
                metrics['connectivity'] * 0.3)

class CityLayoutOptimizer:
    def __init__(self, 
                 streets_data: pd.DataFrame,
                 population_size: int = 50,
                 generations: int = 100,
                 mutation_rate: float = 0.1):
        self.streets_data = streets_data
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.best_layout = None
        
    def _create_initial_population(self) -> List[CityGraph]:
        """Generate initial population of city layouts"""
        population = []
        
        for _ in range(self.population_size):
            city = CityGraph()
            
            # Add all streets
            for _, row in self.streets_data.iterrows():
                street = Street(
                    name=row['Miescowosci (ulice) wchodzace w sklad obwodu'],
                    lat=self._parse_coordinate(row['North']),
                    lon=self._parse_coordinate(row['East'])
                )
                city.add_street(street)
            
            # Randomly connect streets
            street_names = list(city.streets.keys())
            num_connections = random.randint(
                len(street_names), 
                len(street_names) * 2
            )
            
            for _ in range(num_connections):
                street1 = random.choice(street_names)
                street2 = random.choice(street_names)
                if street1 != street2:
                    city.connect_streets(street1, street2)
                    
            population.append(city)
            
        return population
    
    def _parse_coordinate(self, coord: str) -> float:
        """Parse coordinate string to float"""
        if pd.isna(coord):
            return None
        try:
            # Parse format like "51°12'57.70""N"
            parts = coord.replace('"', '').replace('°', ' ').replace("'", ' ').split()
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return degrees + minutes/60 + seconds/3600
        except:
            return None
    
    def _crossover(self, parent1: CityGraph, parent2: CityGraph) -> CityGraph:
        """Perform crossover between two parent layouts"""
        child = CityGraph()
        
        # Copy all streets from parent1
        for street_name, street in parent1.streets.items():
            child.add_street(Street(
                name=street.name,
                lat=street.lat,
                lon=street.lon
            ))
        
        # Inherit connections using a mix of both parents
        all_edges = set(parent1.graph.edges()) | set(parent2.graph.edges())
        for edge in all_edges:
            if random.random() < 0.5:  # 50% chance to inherit each connection
                child.connect_streets(edge[0], edge[1])
                
        return child
    
    def _mutate(self, city: CityGraph) -> CityGraph:
        """Apply random mutations to a city layout"""
        if random.random() < self.mutation_rate:
            # Randomly add or remove some connections
            street_names = list(city.streets.keys())
            
            for _ in range(random.randint(1, 5)):
                street1 = random.choice(street_names)
                street2 = random.choice(street_names)
                
                if street1 != street2:
                    if (street1, street2) in city.graph.edges():
                        city.graph.remove_edge(street1, street2)
                    else:
                        city.connect_streets(street1, street2)
                        
        return city
    
    def _select_parents(self, 
                       population: List[CityGraph], 
                       scores: List[float]) -> Tuple[CityGraph, CityGraph]:
        """Select parents using tournament selection"""
        tournament_size = 3
        selected_parents = []
        
        for _ in range(2):
            tournament_indices = random.sample(
                range(len(population)), 
                tournament_size
            )
            tournament_scores = [scores[i] for i in tournament_indices]
            winner_idx = tournament_indices[np.argmax(tournament_scores)]
            selected_parents.append(population[winner_idx])
            
        return tuple(selected_parents)
    
    def optimize(self) -> CityGraph:
        """Run the genetic algorithm to optimize city layout"""
        population = self._create_initial_population()
        best_score = float('-inf')
        
        for generation in range(self.generations):
            # Evaluate current population
            scores = [city.get_connectivity_score() for city in population]
            
            # Track best layout
            max_score_idx = np.argmax(scores)
            if scores[max_score_idx] > best_score:
                best_score = scores[max_score_idx]
                self.best_layout = population[max_score_idx]
                
            # Create new population
            new_population = []
            
            # Elitism: keep best individual
            new_population.append(population[max_score_idx])
            
            # Create rest of new population
            while len(new_population) < self.population_size:
                # Select parents
                parent1, parent2 = self._select_parents(population, scores)
                
                # Create child through crossover
                child = self._crossover(parent1, parent2)
                
                # Apply mutation
                child = self._mutate(child)
                
                new_population.append(child)
                
            population = new_population
            
            if generation % 10 == 0:
                print(f"Generation {generation}: Best score = {best_score:.4f}")
                
        return self.best_layout

def generate_city_layout(data_file: str) -> CityGraph:
    """Main function to generate optimized city layout"""
    # Read and preprocess data
    df = pd.read_csv(data_file)
    
    # Create and run optimizer
    optimizer = CityLayoutOptimizer(
        streets_data=df,
        population_size=50,
        generations=100,
        mutation_rate=0.1
    )
    
    best_layout = optimizer.optimize()
    return best_layout

# Example usage:
if __name__ == "__main__":
    # Assuming data is saved in 'streets.csv'
    best_city = generate_city_layout('streets.csv')
    
    # Print some statistics about the optimized layout
    print("\nFinal Layout Statistics:")
    print(f"Number of streets: {len(best_city.streets)}")
    print(f"Number of connections: {best_city.graph.number_of_edges()}")
    print(f"Average connections per street: {np.mean([d for _, d in best_city.graph.degree()]):.2f}")
    print(f"Clustering coefficient: {nx.average_clustering(best_city.graph):.2f}")