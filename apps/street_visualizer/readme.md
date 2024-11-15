# Street Visualization Tool

A Python tool for visualizing building layouts and business locations along streets using data from CSV files. This tool is particularly useful for urban planning, historical data visualization, and business distribution analysis.

## 🚀 Quick Start

### Installation

1. Clone the repository and install required dependencies:
```bash
git clone <repository-url>
cd street-visualization
pip install -r requirements.txt
```

2. Required dependencies:
```
pandas>=1.3.0
matplotlib>=3.4.0
```

### Basic Usage

1. Prepare your CSV data file with an 'Address' column containing street names and building numbers.

2. Basic implementation:
```python
from street_visualizer import DataProcessor, StreetVisualizer

# Initialize components
processor = DataProcessor()
visualizer = StreetVisualizer()

# Load and process data
data = processor.load_csv('your_data.csv')
filtered_data = processor.filter_street_data(data, 'YourStreetName')

# Create visualization
visualizer.create_visualization(filtered_data, 'YourStreetName')
```

### Advanced Usage

Customize visualization parameters using `VisualizationConfig`:

```python
from street_visualizer import VisualizationConfig

custom_config = VisualizationConfig(
    street_width=0.07,
    building_width=0.15,
    business_building_color='blue',
    empty_building_color='gray',
    figsize=(15, 10),
    building_alpha=0.8,
    empty_building_alpha=0.3
)

visualizer = StreetVisualizer(custom_config)
```

## 📊 Input Data Format

Your CSV file should include:
- An 'Address' column containing street names and building numbers
- Building numbers should be extractable using regular expressions
- Example format: "Warszawska 12", "12 Warszawska Street"

Example CSV structure:
```csv
Address,Business_Type,Other_Data
Warszawska 12,Restaurant,Data1
14 Warszawska Street,Shop,Data2
```

## 🛠️ Customization Options

The `VisualizationConfig` class supports the following parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| street_width | 0.05 | Width of the street in the visualization |
| building_width | 0.1 | Width of building blocks |
| empty_building_color | 'white' | Color for non-business buildings |
| business_building_color | 'green' | Color for buildings with businesses |
| figsize | (12, 8) | Figure size in inches |
| title_font_size | 12 | Size of title text |
| building_number_font_size | 5 | Size of building number text |
| building_alpha | 1.0 | Opacity of business buildings |
| empty_building_alpha | 0.25 | Opacity of empty buildings |

## 🔄 Future Improvements

### High Priority
1. **Data Handling Enhancements**
   - Support for multiple address formats
   - Better handling of missing or malformed data
   - Support for different CSV column names
   - Data validation and cleansing utilities

2. **Visualization Features**
   - Interactive tooltips showing building information
   - Multiple street comparison in a single view
   - Legend customization options
   - Support for different building shapes/styles
   - Color scheme customization for different business types

3. **Performance Optimization**
   - Batch processing for large datasets
   - Caching mechanism for frequent visualizations
   - Optimized memory usage for large street layouts

### Medium Priority
1. **Export Capabilities**
   - Export to various image formats (PNG, SVG, PDF)
   - Generate report with statistics
   - Save configuration presets

2. **UI/UX Improvements**
   - Command-line interface
   - Configuration file support
   - Progress bars for long operations
   - Interactive parameter adjustment

3. **Analysis Features**
   - Business density calculations
   - Historical change visualization
   - Statistical analysis tools
   - Distance-based clustering

### Long-term Goals
1. **Integration Features**
   - GIS data support
   - Real-time data updates
   - API for external applications
   - Database integration

2. **Advanced Visualization**
   - 3D visualization support
   - Time-series animation
   - Multiple layer support
   - Custom overlay support

3. **Community Features**
   - Template sharing system
   - Plugin architecture
   - Community contribution guidelines
   - Example gallery

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📧 Contact

For questions and support, please open an issue in the repository or contact [maintainer email].