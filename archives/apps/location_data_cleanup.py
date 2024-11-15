import pandas as pd
import numpy as np
from typing import List, Set, Dict
import re
from datetime import datetime

class LocationDataProcessor:
    """Processes location data with deduplication and smart merging"""
    
    def __init__(self):
        self.data = None
        self.processed_data = None
        
    def load_data(self, data: pd.DataFrame) -> None:
        """Load and initialize data"""
        self.data = data.copy()
        
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize location names for comparison"""
        # Remove common variations
        name = name.lower()
        name = name.replace("'s", "")
        name = re.sub(r'\s+\(.*?\)', '', name)  # Remove parenthetical descriptions
        name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
        return name.strip()
    
    @staticmethod
    def merge_years(years_str1: str, years_str2: str) -> str:
        """Merge year entries, handling various formats"""
        # Extract all years from both strings
        years: Set[str] = set()
        
        for years_str in [years_str1, years_str2]:
            if pd.isna(years_str) or years_str == "Not specified":
                continue
                
            # Handle various year formats
            matches = re.findall(r'\d{4}|\d{2}th Century', years_str)
            years.update(matches)
            
            # Handle special cases like "5660s"
            if '5660s' in years_str:
                years.add('early 20th century')
                
        if not years:
            return "Not specified"
            
        # Sort years chronologically
        sorted_years = sorted(years, key=lambda x: x if 'Century' in x else int(x))
        return ", ".join(sorted_years)
    
    @staticmethod
    def merge_descriptions(desc1: str, desc2: str) -> str:
        """Merge descriptions, avoiding redundancy"""
        if pd.isna(desc1) or desc1 == "":
            return desc2
        if pd.isna(desc2) or desc2 == "":
            return desc1
            
        # Split descriptions into sentences
        sentences1 = set(re.split(r'[.!?]+', desc1))
        sentences2 = set(re.split(r'[.!?]+', desc2))
        
        # Combine unique sentences
        all_sentences = sentences1.union(sentences2)
        all_sentences = {s.strip() for s in all_sentences if s.strip()}
        
        return ". ".join(sorted(all_sentences)) + "."
    
    def find_duplicates(self) -> Dict[str, List[int]]:
        """Find duplicate entries based on normalized names"""
        name_groups = {}
        
        for idx, row in self.data.iterrows():
            norm_name = self.normalize_name(row['name'])
            if norm_name not in name_groups:
                name_groups[norm_name] = []
            name_groups[norm_name].append(idx)
            
        # Return only groups with multiple entries
        return {name: indices for name, indices 
                in name_groups.items() 
                if len(indices) > 1}
    
    def merge_duplicate_rows(self, indices: List[int]) -> pd.Series:
        """Merge multiple rows into a single row"""
        rows = self.data.loc[indices]
        
        # Start with the most complete row (one with most non-null values)
        completeness_scores = rows.notna().sum(axis=1)
        base_row = rows.loc[completeness_scores.idxmax()].copy()
        
        # Merge information from other rows
        for idx in indices:
            if idx == completeness_scores.idxmax():
                continue
                
            row = rows.loc[idx]
            
            # Merge years
            base_row['year_mentioned'] = self.merge_years(
                base_row['year_mentioned'],
                row['year_mentioned']
            )
            
            # Merge descriptions
            base_row['description'] = self.merge_descriptions(
                base_row['description'],
                row['description']
            )
            
            # Keep location_within_kowel_city_limits if either is Yes
            if row['location_within_kowel_city_limits'] == 'Yes':
                base_row['location_within_kowel_city_limits'] = 'Yes'
                
        return base_row
    
    def process_data(self) -> pd.DataFrame:
        """Process data to remove and merge duplicates"""
        if self.data is None:
            raise ValueError("No data loaded")
            
        # Find duplicate groups
        duplicate_groups = self.find_duplicates()
        
        # Create new dataframe for processed data
        processed_rows = []
        processed_indices = set()
        
        # Process duplicate groups
        for norm_name, indices in duplicate_groups.items():
            merged_row = self.merge_duplicate_rows(indices)
            processed_rows.append(merged_row)
            processed_indices.update(indices)
            
        # Add non-duplicate rows
        for idx, row in self.data.iterrows():
            if idx not in processed_indices:
                processed_rows.append(row)
                
        # Create new dataframe and sort by name
        self.processed_data = pd.DataFrame(processed_rows)
        self.processed_data = self.processed_data.sort_values('name')
        
        return self.processed_data
    
    def save_to_csv(self, filename: str) -> None:
        """Save processed data to CSV"""
        if self.processed_data is None:
            raise ValueError("No processed data available")
        self.processed_data.to_csv(filename, index=False)

def main():
    # Read data
    df = pd.read_csv('locations.csv')
    
    # Initialize processor
    processor = LocationDataProcessor()
    
    # Load and process data
    processor.load_data(df)
    processed_df = processor.process_data()
    
    # Save results
    processor.save_to_csv('processed_locations.csv')
    
    # Print statistics
    print(f"Original rows: {len(df)}")
    print(f"Processed rows: {len(processed_df)}")
    print(f"Duplicates merged: {len(df) - len(processed_df)}")
    
    # Display example of merged entries
    print("\nExample of merged entries:")
    duplicate_groups = processor.find_duplicates()
    if duplicate_groups:
        example_group = list(duplicate_groups.values())[0]
        print("\nOriginal entries:")
        print(df.loc[example_group])
        print("\nMerged entry:")
        print(processor.merge_duplicate_rows(example_group))

if __name__ == "__main__":
    main()