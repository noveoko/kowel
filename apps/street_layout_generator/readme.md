# City Layout Generator

A Python-based tool that uses Network Science and Genetic Programming to generate optimized city street layouts. This project combines graph theory and evolutionary algorithms to create realistic and efficient street networks based on connectivity patterns.

## 🌟 Features

- **Network-Based Street Layout Generation**: Uses NetworkX to create and analyze street networks
- **Genetic Algorithm Optimization**: Evolves street layouts to find optimal configurations
- **Geographic Coordinate Support**: Handles real-world coordinates for street positioning
- **Flexible Fitness Metrics**: Evaluates layouts based on multiple network characteristics:
  - Average street connectivity
  - Clustering coefficient
  - Network resilience
- **Customizable Parameters**: Adjust genetic algorithm parameters to fine-tune the generation process

## 📋 Prerequisites

```bash
pip install networkx pandas numpy
```

## 🚀 Quick Start

1. **Prepare Your Data**
   Create a CSV file with your street data in the following format:
   ```csv
   Nr. Obwodu,Adres biura komisji i lokalu wyborczego,Miescowosci (ulice) wchodzace w sklad obwodu,Photo of building on this street,North,East
   1,Location A,Street Name 1,,,51°12'57.70"N,24°41'54.08"E
   ```

2. **Generate a Layout**
   ```python
   from city_layout_generator import generate_city_layout
   
   # Generate optimized layout
   best_city = generate_city_layout('your_streets.csv')
   
   # Print statistics
   print(f"Number of streets: {len(best_city.streets)}")
   print(f"Number of connections: {best_city.graph.number_of_edges()}")
   ```

## 🔧 Configuration

The `CityLayoutOptimizer` class accepts several parameters to customize the generation process:

```python
optimizer = CityLayoutOptimizer(
    streets_data=df,
    population_size=50,    # Size of each generation
    generations=100,       # Number of generations to evolve
    mutation_rate=0.1      # Probability of mutation
)
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| population_size | 50 | Number of layouts in each generation |
| generations | 100 | Number of evolution cycles |
| mutation_rate | 0.1 | Probability of random mutations |

## 📊 How It Works

### 1. Network Representation
- Streets are represented as nodes in a graph
- Connections between streets are represented as edges
- Geographic coordinates are preserved for spatial analysis

### 2. Genetic Algorithm Process
1. **Initialization**: Creates random initial street layouts
2. **Evaluation**: Scores layouts based on network metrics
3. **Selection**: Uses tournament selection to choose parent layouts
4. **Crossover**: Combines parent layouts to create new ones
5. **Mutation**: Randomly modifies some connections
6. **Repetition**: Repeats the process for specified generations

### 3. Fitness Evaluation
The fitness score combines multiple metrics:
- 40% - Average degree (connectivity)
- 30% - Clustering coefficient
- 30% - Network edge connectivity

## 🎯 Use Cases

- Urban Planning: Generate initial street layout proposals
- Traffic Analysis: Optimize street connectivity for better flow
- City Growth Simulation: Model potential city expansion patterns
- Network Analysis: Study street network characteristics

## 🔍 Advanced Usage

### Custom Fitness Functions

You can modify the `get_connectivity_score` method in `CityGraph` to use different metrics:

```python
def get_connectivity_score(self) -> float:
    metrics = {
        'avg_degree': np.mean([d for _, d in self.graph.degree()]),
        'clustering': nx.average_clustering(self.graph),
        'connectivity': nx.edge_connectivity(self.graph) 
                       if nx.is_connected(self.graph) else 0
    }
    
    # Customize weights
    return (metrics['avg_degree'] * 0.4 + 
            metrics['clustering'] * 0.3 + 
            metrics['connectivity'] * 0.3)
```

### Mutation Customization

Adjust mutation behavior by modifying the `_mutate` method:

```python
def _mutate(self, city: CityGraph) -> CityGraph:
    if random.random() < self.mutation_rate:
        # Add your custom mutation logic here
        pass
    return city
```

## 📈 Performance Optimization

For large street networks:
1. Use smaller population sizes initially
2. Implement parallel fitness evaluation
3. Cache network metrics calculations
4. Use sparse graph representations

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional network metrics
- Visualization tools
- Performance optimizations
- Real-world validation tools

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📚 References

- NetworkX Documentation: [https://networkx.org/documentation/stable/](https://networkx.org/documentation/stable/)
- Network Science Book: [http://networksciencebook.com/](http://networksciencebook.com/)
- Urban Network Analysis: [https://doi.org/10.1016/j.compenvurbsys.2010.10.002](https://doi.org/10.1016/j.compenvurbsys.2010.10.002)