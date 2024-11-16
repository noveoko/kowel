import csv
from typing import List
import re

def clean_fields(fields: List[str]) -> List[str]:
    """Clean and format fields from a CSV row."""
    print(f"Processing row with {len(fields)} fields: {fields}")  # Debug print
    
    # Handle different number of fields
    while len(fields) < 6:
        fields.append("")  # Pad with empty strings if needed
    
    if len(fields) >= 6:
        date, names, location, description, tags, *extra = fields
    else:
        print(f"Warning: Row has fewer than expected fields: {fields}")
        return fields
    
    # Clean date
    date = date.strip()
    if ',' not in date:
        match = re.match(r'(\w+ \d+) (\d{4})', date)
        if match:
            date = f"{match.group(1)}, {match.group(2)}"
    
    # Clean names
    names = names.strip()
    names = re.sub(r'\s*;\s*', ' & ', names)
    
    # Clean location
    location = location.strip()
    
    # Clean description
    description = description.strip()
    description = description.replace('"', "'").replace('"', "'").replace('"', "'")
    description = re.sub(r',(\S)', r', \1', description)
    description = re.sub(r';(\S)', r'; \1', description)
    description = re.sub(r'\.(\S)', r'. \1', description)
    description = re.sub(r'\s+', ' ', description)
    
    # Clean tags
    tags = tags.strip()
    tag_list = [tag.strip() for tag in tags.split(';')]
    tags = ';'.join(tag_list)
    
    return [date, names, location, description, tags, ""]  # Adding empty 6th column

def process_csv(input_file: str, output_file: str):
    """Process entire CSV file and write cleaned data to new file."""
    try:
        # Read input CSV and print structure
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            rows = list(reader)
            print(f"Input file has {len(rows)} rows")
            for i, row in enumerate(rows):
                print(f"Row {i} has {len(row)} fields")
        
        # Clean all rows
        cleaned_rows = [clean_fields(row) for row in rows]
        
        # Write cleaned data to new file
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(cleaned_rows)
            
        print(f"Successfully processed {len(cleaned_rows)} rows")
        print(f"Cleaned data written to {output_file}")
        
        # Print first few rows of output for verification
        print("\nFirst few rows of output:")
        for i, row in enumerate(cleaned_rows[:3]):
            print(f"Row {i}: {row}")
        
    except FileNotFoundError:
        print(f"Error: Could not find input file {input_file}")
    except Exception as e:
        print(f"Error processing file: {str(e)}")

# Example usage
if __name__ == "__main__":
    input_file = "/content/newspapers.csv"
    output_file = "/content/read_newspapers.csv"
    process_csv(input_file, output_file)
