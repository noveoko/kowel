import dataclasses
from typing import List, Dict, Optional
import re
from collections import defaultdict

@dataclasses.dataclass
class Business:
    name: str
    street: str
    number: Optional[int]
    type: str
    
    @classmethod
    def parse_address(cls, address: str) -> tuple[str, Optional[int]]:
        """Extract street name and number from address string."""
        if not address:
            return "", None
        
        # Try to find number at the end
        match = re.search(r'(\d+)$', address.strip())
        if match:
            number = int(match.group(1))
            street = address[:match.start()].strip()
            return street, number
        return address.strip(), None

class StreetVisualizer:
    # Industry type to color mapping
    INDUSTRY_COLORS = {
        'factory': '#FFA500',
        'retail': '#4CAF50',
        'services': '#2196F3',
        'food': '#F44336',
        'craftsman': '#9C27B0',
        'transport': '#795548',
        'other': '#9E9E9E',
    }
    
    # Industry classification mapping
    INDUSTRY_MAPPING = {
        'Tytoniowe wyroby fabryki': 'factory',
        'Wody gazowe fabryki': 'factory',
        'Tartaki': 'factory',
        'Garbarnie': 'factory',
        'Zegarmistrz': 'services',
        'Fryzjerzy': 'services',
        'Fotograficzne zakłady': 'services',
        'Hotele': 'services',
        'Jubilerzy': 'retail',
        'Kapelusze': 'retail',
        'Ubrania gotowe': 'retail',
        'Księgarnie': 'retail',
        'Żelazo': 'retail',
        'Jadłodajnie': 'food',
        'Cukiernia': 'food',
        'Wędliny': 'food',
        'Stolarze': 'craftsman',
        'Szewcy': 'craftsman',
        'Krawcy': 'craftsman',
        'Zajazdy': 'transport',
    }

    def __init__(self, width: int = 1000, height: int = 400, padding: int = 50):
        self.width = width
        self.height = height
        self.padding = padding
        
    def get_industry_category(self, business_type: str) -> str:
        """Map business type to industry category."""
        return self.INDUSTRY_MAPPING.get(business_type, 'other')
    
    def generate_svg(self, businesses: List[Business], street_name: str) -> str:
        # Filter businesses for given street and with valid numbers
        street_businesses = [b for b in businesses 
                           if b.street == street_name and b.number is not None]
        
        if not street_businesses:
            return f"<svg><text x='10' y='20'>No businesses found for {street_name}</text></svg>"
        
        # Split into even/odd numbers
        even_businesses = sorted([b for b in street_businesses if b.number % 2 == 0], 
                               key=lambda x: x.number)
        odd_businesses = sorted([b for b in street_businesses if b.number % 2 == 1], 
                              key=lambda x: x.number)
        
        # Find the range of numbers
        all_numbers = [b.number for b in street_businesses]
        min_number = min(all_numbers)
        max_number = max(all_numbers)
        number_range = max_number - min_number
        
        # Calculate scaling factor for positioning
        usable_width = self.width - (2 * self.padding)
        scale = usable_width / number_range if number_range > 0 else 1
        
        svg_elements = []
        
        # Start SVG with background and title
        svg_elements.extend([
            f'<svg viewBox="0 0 {self.width} {self.height}" xmlns="http://www.w3.org/2000/svg">',
            f'<style>',
            '.business-label { font-size: 10px; }',
            '.street-name { font-size: 20px; font-weight: bold; }',
            '.tooltip { font-size: 12px; }',
            '</style>',
            f'<rect width="{self.width}" height="{self.height}" fill="#f0f0f0"/>',
            f'<text x="{self.width/2}" y="30" text-anchor="middle" class="street-name">{street_name}</text>'
        ])
        
        # Draw street line
        street_y = self.height / 2
        svg_elements.append(
            f'<line x1="{self.padding}" y1="{street_y}" '
            f'x2="{self.width-self.padding}" y2="{street_y}" '
            f'stroke="gray" stroke-width="2"/>'
        )
        
        # Generate legend
        legend_y = self.height - 30
        legend_x = self.padding
        for industry, color in self.INDUSTRY_COLORS.items():
            svg_elements.extend([
                f'<rect x="{legend_x}" y="{legend_y}" width="15" height="15" fill="{color}"/>',
                f'<text x="{legend_x + 20}" y="{legend_y + 12}" class="business-label">{industry}</text>'
            ])
            legend_x += 100
        
        # Function to generate business marker
        def add_business_marker(business, y_offset):
            industry = self.get_industry_category(business.type)
            color = self.INDUSTRY_COLORS[industry]
            
            x_pos = self.padding + ((business.number - min_number) * scale)
            y_pos = street_y + y_offset
            
            marker_elements = [
                f'<g class="business-marker">',
                f'<rect x="{x_pos-10}" y="{y_pos-10}" width="20" height="20" fill="{color}" rx="4"/>',
                f'<text x="{x_pos}" y="{y_pos+25}" text-anchor="middle" class="business-label">',
                f'№{business.number}</text>',
                '<title>',
                f'{business.name}\n{business.type}\n{street_name} {business.number}',
                '</title>',
                '</g>'
            ]
            return marker_elements
        
        # Add business markers
        for business in even_businesses:
            svg_elements.extend(add_business_marker(business, -40))
        
        for business in odd_businesses:
            svg_elements.extend(add_business_marker(business, 40))
        
        # Close SVG
        svg_elements.append('</svg>')
        
        return '\n'.join(svg_elements)

def parse_business_data(data: List[Dict]) -> List[Business]:
    """Parse raw business data into Business objects."""
    businesses = []
    for item in data:
        street, number = Business.parse_address(item.get('address', ''))
        businesses.append(Business(
            name=item.get('name', ''),
            street=street,
            number=number,
            type=item.get('type', 'other')
        ))
    return businesses

# Example usage
if __name__ == "__main__":
    # Example data
    sample_data = [
        {"name": "Hotel Bristol", "address": "Warszawska 28", "type": "Hotele"},
        {"name": "Cukiernia Bauch", "address": "Warszawska 14", "type": "Cukiernia"},
        {"name": "Księgarnia Berelzon", "address": "Warszawska 58", "type": "Księgarnie"},
        {"name": "Sklep Żelazny", "address": "Warszawska 31", "type": "Żelazo"},
        {"name": "Fryzjer Fajner", "address": "Warszawska 31", "type": "Fryzjerzy"},
        {"name": "Zegarmistrz Buruk", "address": "Warszawska 22", "type": "Zegarmistrz"},
    ]
    
    # Parse data and create visualization
    businesses = parse_business_data(sample_data)
    visualizer = StreetVisualizer()
    svg_output = visualizer.generate_svg(businesses, "Warszawska")
    
    # Save to file
    with open("street_visualization.svg", "w", encoding="utf-8") as f:
        f.write(svg_output)