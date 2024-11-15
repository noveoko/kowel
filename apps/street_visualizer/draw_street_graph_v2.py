from dataclasses import dataclass
from typing import Optional, Tuple
import matplotlib.pyplot as plt
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class VisualizationConfig:
    """Configuration settings for street visualization."""
    street_width: float = 0.05
    building_width: float = 0.1
    empty_building_color: str = 'white'
    business_building_color: str = 'green'
    figsize: Tuple[int, int] = (12, 8)
    title_font_size: int = 12
    building_number_font_size: int = 5
    building_alpha: float = 1.0
    empty_building_alpha: float = 0.25

class DataProcessor:
    """Handles data loading and processing operations."""
    
    @staticmethod
    def load_csv(path: str) -> Optional[pd.DataFrame]:
        """
        Load data from a CSV file.
        
        Args:
            path: Path to the CSV file.
            
        Returns:
            DataFrame or None if loading fails.
        """
        try:
            return pd.read_csv(path)
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            return None

    @staticmethod
    def filter_street_data(df: pd.DataFrame, street_name: str) -> Optional[pd.DataFrame]:
        """
        Filter DataFrame for specific street and extract building numbers.
        
        Args:
            df: Input DataFrame.
            street_name: Name of the street to filter for.
            
        Returns:
            Filtered DataFrame with building numbers or None if processing fails.
        """
        try:
            if 'Address' not in df.columns:
                raise ValueError("DataFrame must contain 'Address' column")
                
            df_filtered = df[df['Address'].str.contains(street_name, case=False, na=False)].copy()
            df_filtered['Building Number'] = df_filtered['Address'].str.extract(r'(\d+)').astype(float)
            return df_filtered
            
        except Exception as e:
            logger.error(f"Error processing street data: {e}")
            return None

class StreetVisualizer:
    """Handles the visualization of street layouts."""
    
    def __init__(self, config: Optional[VisualizationConfig] = None):
        """
        Initialize visualizer with configuration.
        
        Args:
            config: VisualizationConfig object with visualization parameters.
        """
        self.config = config or VisualizationConfig()

    def _setup_plot(self, max_building_number: int) -> Tuple[plt.Figure, plt.Axes]:
        """Set up the plot with basic configuration."""
        fig, ax = plt.subplots(figsize=self.config.figsize)
        ax.set_ylim(0, 1)
        ax.set_xlim(0, max_building_number + 2)
        ax.axis('off')
        return fig, ax

    def _add_building(self, ax: plt.Axes, building_num: int, is_business: bool, y_pos: float, label_y: float):
        """Add a single building to the plot."""
        building_color = (self.config.business_building_color if is_business 
                         else self.config.empty_building_color)
        alpha = (self.config.building_alpha if is_business 
                else self.config.empty_building_alpha)
        
        ax.add_patch(plt.Rectangle(
            (building_num, y_pos), 1, self.config.building_width,
            facecolor=building_color, edgecolor='black', alpha=alpha
        ))
        
        if is_business:
            ax.text(
                building_num + 0.5, label_y, str(int(building_num)),
                ha='center', va='center', fontsize=self.config.building_number_font_size,
                color='black', rotation=90
            )

    def create_visualization(self, data: pd.DataFrame, street_name: str) -> None:
        """
        Create and display the street visualization.
        
        Args:
            data: Processed DataFrame containing building information.
            street_name: Name of the street being visualized.
        """
        try:
            max_building_number = int(data['Building Number'].max())
            fig, ax = self._setup_plot(max_building_number)
            
            for i in range(1, max_building_number + 1):
                # Calculate positions
                if i % 2 == 0:  # Even numbers (top side)
                    y = 0.5 + self.config.street_width / 2
                    label_y = y + self.config.building_width + 0.02
                else:  # Odd numbers (bottom side)
                    y = 0.5 - self.config.street_width / 2 - self.config.building_width
                    label_y = y - 0.02
                
                is_business = i in data['Building Number'].values
                self._add_building(ax, i, is_business, y, label_y)
            
            # Add labels and title
            self._add_labels(ax, street_name, max_building_number)
            plt.tight_layout()
            plt.show()
            
        except Exception as e:
            logger.error(f"Error creating visualization: {e}")

    def _add_labels(self, ax: plt.Axes, street_name: str, max_building_number: int):
        """Add street name and side labels to the visualization."""
        ax.text((max_building_number + 2) / 2, 0.5, street_name,
                ha='center', va='center', fontsize=self.config.title_font_size)
        
        right_side_label_y = 0.5 + self.config.street_width / 2 + self.config.building_width + 0.05
        left_side_label_y = 0.5 - self.config.street_width / 2 - self.config.building_width - 0.13
        
        ax.text(max_building_number + 1, left_side_label_y, "Left Side", ha='center', rotation=90)
        ax.text(max_building_number + 1, right_side_label_y, "Right Side", ha='center', rotation=90)
        ax.set_title("Kowel 1929 Known Businesses by Street")

def main():
    """Main function to demonstrate usage."""
    # Custom configuration (optional)
    config = VisualizationConfig(
        street_width=0.05,
        building_width=0.1,
        business_building_color='green',
        figsize=(12, 8)
    )
    
    # Initialize components
    processor = DataProcessor()
    visualizer = StreetVisualizer(config)
    
    # Process data
    input_data = processor.load_csv('population.csv')
    if input_data is None:
        return
        
    df_filtered = processor.filter_street_data(input_data, 'Warszawska')
    if df_filtered is None:
        return
        
    # Create visualization
    visualizer.create_visualization(df_filtered, 'Warszawska')

if __name__ == "__main__":
    main()