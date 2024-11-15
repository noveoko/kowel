import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator, ValidationError
from typing import List, Optional, Dict, Any
import re
from datetime import datetime
import unicodedata
from collections import defaultdict
import logging
from pathlib import Path
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('refugee_data_processing.log'),
        logging.StreamHandler()
    ]
)

class PersonName(BaseModel):
    """Model for handling person names with various formats"""
    full_name: str
    surname: str
    given_names: List[str]
    nickname: Optional[str] = None
    
    @validator('full_name')
    def normalize_full_name(cls, v):
        """Normalize full name to handle various character encodings"""
        return unicodedata.normalize('NFKC', v.strip())
    
    @validator('given_names', pre=True)
    def split_given_names(cls, v):
        """Split given names if provided as string"""
        if isinstance(v, str):
            return [name.strip() for name in v.split(',')]
        return v

class Person(BaseModel):
    """Main model for person data"""
    name_data: PersonName
    birthdate: str
    nationality: str
    additional_info: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('birthdate')
    def validate_birthdate(cls, v):
        """Validate and normalize date format"""
        if v == 'UNBEKANNT':
            return v
        
        try:
            # Parse and standardize date format
            date_obj = datetime.strptime(v, '%d.%m.%Y')
            return date_obj.strftime('%d.%m.%Y')
        except ValueError:
            raise ValueError(f'Invalid date format: {v}')
    
    @validator('nationality')
    def normalize_nationality(cls, v):
        """Normalize nationality field"""
        return v.strip().upper()

class RefugeeDataProcessor:
    """Main class for processing refugee data"""
    
    def __init__(self, input_file: str = None):
        self.input_file = input_file
        self.processed_data: List[Person] = []
        self.statistics: Dict[str, Any] = {}
        self.errors: List[Dict[str, Any]] = []
        
    def load_raw_data(self, data_source: Any) -> List[Dict[str, Any]]:
        """Load data from various source formats"""
        if isinstance(data_source, str):
            # Load from file
            file_ext = Path(data_source).suffix.lower()
            if file_ext == '.json':
                with open(data_source, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif file_ext in ['.txt', '.csv']:
                return pd.read_csv(data_source).to_dict('records')
        elif isinstance(data_source, list):
            return data_source
        raise ValueError(f"Unsupported data source format: {type(data_source)}")

    def parse_name(self, raw_name: str) -> Dict[str, Any]:
        """Parse complex name formats"""
        # Handle various name patterns
        name_parts = raw_name.strip().split()
        
        # Handle compound surnames
        surname_parts = []
        given_names = []
        
        for part in name_parts:
            if part.isupper() or '-' in part:
                surname_parts.append(part)
            else:
                given_names.append(part)
                
        surname = ' '.join(surname_parts)
        
        return {
            'full_name': raw_name,
            'surname': surname,
            'given_names': given_names
        }

    def process_record(self, record: Dict[str, Any]) -> Optional[Person]:
        """Process individual records with error handling"""
        try:
            # Extract and parse name data
            name_data = self.parse_name(record.get('name', ''))
            
            # Create person object
            person = Person(
                name_data=PersonName(**name_data),
                birthdate=record.get('birthdate', 'UNBEKANNT'),
                nationality=record.get('country', 'UNBEKANNT'),
                additional_info={
                    'nickname': record.get('nickname'),
                    'source_record': record
                }
            )
            return person
            
        except ValidationError as e:
            self.errors.append({
                'record': record,
                'error': str(e),
                'type': 'validation_error'
            })
            logging.error(f"Validation error processing record: {record}")
            return None
        except Exception as e:
            self.errors.append({
                'record': record,
                'error': str(e),
                'type': 'processing_error'
            })
            logging.error(f"Error processing record: {record}")
            return None

    def process_data(self, data_source: Any) -> None:
        """Process all records and compile statistics"""
        raw_data = self.load_raw_data(data_source)
        
        # Process records
        for record in raw_data:
            person = self.process_record(record)
            if person:
                self.processed_data.append(person)
        
        # Compile statistics
        self.compute_statistics()
        
    def compute_statistics(self) -> None:
        """Compute various statistics about the processed data"""
        stats = defaultdict(int)
        
        # Basic counts
        stats['total_records'] = len(self.processed_data)
        stats['error_count'] = len(self.errors)
        
        # Nationality distribution
        nationality_counts = defaultdict(int)
        for person in self.processed_data:
            nationality_counts[person.nationality] += 1
        stats['nationality_distribution'] = dict(nationality_counts)
        
        # Year distribution
        year_counts = defaultdict(int)
        for person in self.processed_data:
            if person.birthdate != 'UNBEKANNT':
                year = person.birthdate.split('.')[-1]
                year_counts[year] += 1
        stats['birth_year_distribution'] = dict(year_counts)
        
        self.statistics = dict(stats)

    def export_data(self, output_format: str = 'csv') -> None:
        """Export processed data in various formats"""
        if output_format == 'csv':
            self.export_to_csv('processed_refugee_data.csv')
        elif output_format == 'json':
            self.export_to_json('processed_refugee_data.json')
        
        # Export statistics
        with open('processing_statistics.json', 'w', encoding='utf-8') as f:
            json.dump(self.statistics, f, indent=2)
            
        # Export errors if any
        if self.errors:
            with open('processing_errors.json', 'w', encoding='utf-8') as f:
                json.dump(self.errors, f, indent=2)

    def export_to_csv(self, filename: str) -> None:
        """Export data to CSV format"""
        records = []
        for person in self.processed_data:
            record = {
                'Surname': person.name_data.surname,
                'Given Names': ', '.join(person.name_data.given_names),
                'Full Name': person.name_data.full_name,
                'Birthdate': person.birthdate,
                'Nationality': person.nationality,
                'Nickname': person.additional_info.get('nickname', '')
            }
            records.append(record)
            
        df = pd.DataFrame(records)
        df.to_csv(filename, index=False, encoding='utf-8')

    def export_to_json(self, filename: str) -> None:
        """Export data to JSON format"""
        records = [person.dict() for person in self.processed_data]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2)

# Example usage
if __name__ == "__main__":
    # Initialize processor
    processor = RefugeeDataProcessor()
    
    # Sample data
    sample_data = [
        {
            "name": "Heinrich GALINSKY",
            "birthdate": "29.01.1928",
            "country": "POLEN",
            "nickname": "Henri"
        }
    ]
    
    # Process data
    processor.process_data(sample_data)
    
    # Export results
    processor.export_data(output_format='csv')
    
    # Print statistics
    print("\nProcessing Statistics:")
    for key, value in processor.statistics.items():
        print(f"{key}: {value}")