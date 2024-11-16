import csv
from typing import List, Tuple, Set
from difflib import SequenceMatcher
import pandas as pd
from datetime import datetime
import re

class DuplicateFinder:
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.date_pattern = re.compile(r'\b\w+ \d+,? \d{4}\b')
        self.expected_fields = ['date', 'names', 'location', 'description', 'tags']
        self.weights = {
            'date': 0.3,
            'names': 0.3,
            'location': 0.2,
            'description': 0.1,
            'tags': 0.1
        }
    
    def normalize_row(self, row: List[str]) -> List[str]:
        """Ensure row has correct number of fields."""
        # Pad short rows with empty strings
        if len(row) < len(self.expected_fields):
            row = row + [''] * (len(self.expected_fields) - len(row))
        # Truncate long rows
        return row[:len(self.expected_fields)]

    def calculate_similarity(self, row1: List[str], row2: List[str]) -> float:
        """Calculate similarity between two rows using a weighted approach."""
        # Normalize rows to ensure they have the same number of fields
        row1 = self.normalize_row(row1)
        row2 = self.normalize_row(row2)
        
        total_similarity = 0.0
        
        for i, (field1, field2) in enumerate(zip(row1, row2)):
            field_name = self.expected_fields[i]
            field1 = str(field1) if field1 is not None else ''
            field2 = str(field2) if field2 is not None else ''
            
            # Special handling for dates
            if field_name == 'date':
                date1 = self.date_pattern.search(field1)
                date2 = self.date_pattern.search(field2)
                if date1 and date2:
                    similarity = SequenceMatcher(None, date1.group(), date2.group()).ratio()
                else:
                    similarity = SequenceMatcher(None, field1, field2).ratio()
            
            # Special handling for tags
            elif field_name == 'tags':
                tags1 = set(t.strip().lower() for t in field1.split(';') if t.strip())
                tags2 = set(t.strip().lower() for t in field2.split(';') if t.strip())
                if tags1 or tags2:
                    similarity = len(tags1 & tags2) / len(tags1 | tags2)
                else:
                    similarity = 1.0 if not tags1 and not tags2 else 0.0
            
            else:
                # Standard string similarity for other fields
                similarity = SequenceMatcher(None, str(field1).lower(), str(field2).lower()).ratio()
            
            total_similarity += similarity * self.weights[field_name]
        
        return total_similarity

    def find_duplicates(self, rows: List[List[str]]) -> List[Tuple[int, int, float]]:
        """Find pairs of similar rows with their similarity scores."""
        duplicates = []
        total_comparisons = len(rows) * (len(rows) - 1) // 2
        
        print(f"Comparing {total_comparisons} row pairs...")
        comparison_count = 0
        
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                try:
                    similarity = self.calculate_similarity(rows[i], rows[j])
                    if similarity >= self.similarity_threshold:
                        duplicates.append((i, j, similarity))
                    
                    comparison_count += 1
                    if comparison_count % 10000 == 0:
                        print(f"Processed {comparison_count}/{total_comparisons} comparisons...")
                        
                except Exception as e:
                    print(f"Error comparing rows {i} and {j}: {str(e)}")
                    print(f"Row {i}: {rows[i]}")
                    print(f"Row {j}: {rows[j]}")
                    continue
        
        return duplicates

def process_csv(input_file: str, output_file: str, similarity_threshold: float = 0.85):
    """Process CSV file and remove similar rows."""
    try:
        # Read input CSV
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            rows = list(reader)
        
        print(f"Read {len(rows)} rows from input file")
        
        # Print first few rows for debugging
        print("\nFirst few rows:")
        for i, row in enumerate(rows[:3]):
            print(f"Row {i}: {row} (length: {len(row)})")
        
        # Find duplicates
        finder = DuplicateFinder(similarity_threshold)
        duplicates = finder.find_duplicates(rows)
        
        # Print duplicate information
        if duplicates:
            print(f"\nFound {len(duplicates)} potential duplicate pairs:")
            for i, j, similarity in duplicates[:5]:  # Show first 5 duplicates
                print(f"\nSimilarity: {similarity:.2f}")
                print(f"Row {i}: {rows[i]}")
                print(f"Row {j}: {rows[j]}")
            
            # Get indices to remove (keep the first occurrence)
            to_remove = set()
            for _, j, _ in duplicates:
                to_remove.add(j)
            
            # Create new rows without duplicates
            cleaned_rows = [row for i, row in enumerate(rows) if i not in to_remove]
            
            print(f"\nRemoving {len(to_remove)} duplicate rows")
            
            # Write cleaned data
            with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
                writer.writerows(cleaned_rows)
            
            print(f"Successfully wrote {len(cleaned_rows)} rows to {output_file}")
        else:
            print("No duplicates found")
            # Write original data if no duplicates found
            with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
                writer.writerows(rows)
    
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        raise  # Re-raise the exception to see the full traceback

if __name__ == "__main__":
    input_file = "/content/read_newspapers.csv"
    output_file = "/content/cleaned_up.csv"
    similarity_threshold = 0.85  # Adjust this value to be more or less strict
    process_csv(input_file, output_file, similarity_threshold)
