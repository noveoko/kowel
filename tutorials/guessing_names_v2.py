import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import math
from collections import defaultdict
import Levenshtein
from sklearn.metrics import mean_squared_error
from scipy.stats import norm

@dataclass
class StreetNameFeatures:
    name: str
    length_chars: int
    pixel_width: float
    char_density: float  # pixels per character
    
    @classmethod
    def from_measurement(cls, name: str, pixel_width: float):
        return cls(
            name=name,
            length_chars=len(name),
            pixel_width=pixel_width,
            char_density=pixel_width / len(name)
        )

class PixelDensityAnalyzer:
    """Analyzes character density patterns in street names"""
    
    def __init__(self):
        self.char_densities = defaultdict(list)
        self.global_density_stats = None
        
    def add_measurement(self, name: str, pixel_width: float):
        features = StreetNameFeatures.from_measurement(name, pixel_width)
        self.char_densities[len(name)].append(features.char_density)
        
    def compute_statistics(self):
        """Compute global and length-specific density statistics"""
        all_densities = [d for densities in self.char_densities.values() 
                        for d in densities]
        
        self.global_density_stats = {
            'mean': np.mean(all_densities),
            'std': np.std(all_densities),
            'length_specific': {
                length: {
                    'mean': np.mean(densities),
                    'std': np.std(densities) if len(densities) > 1 else 0
                }
                for length, densities in self.char_densities.items()
            }
        }
        
    def get_density_probability(self, length: int, density: float) -> float:
        """Calculate probability of a density given character length"""
        if not self.global_density_stats:
            self.compute_statistics()
            
        # Use length-specific stats if available, otherwise fall back to global
        if length in self.global_density_stats['length_specific']:
            stats = self.global_density_stats['length_specific'][length]
            return norm.pdf(density, stats['mean'], stats['std'] + 1e-6)
        else:
            return norm.pdf(density, 
                          self.global_density_stats['mean'],
                          self.global_density_stats['std'])

class EnhancedStringPredictor:
    def __init__(self):
        self.rf_model = RandomForestRegressor(n_estimators=100, 
                                            min_samples_leaf=2)
        self.gb_model = GradientBoostingRegressor(n_estimators=100,
                                                 learning_rate=0.1)
        self.scaler = StandardScaler()
        self.density_analyzer = PixelDensityAnalyzer()
        self.characteristic_ratios = {}
        
    def add_training_data(self, 
                         chars: List[int], 
                         lengths: List[float], 
                         names: Optional[List[str]] = None):
        """Add training data and compute characteristic ratios"""
        if names:
            for name, pixel_width in zip(names, lengths):
                self.density_analyzer.add_measurement(name, pixel_width)
                
        # Compute characteristic width/height ratios for different characters
        if names:
            char_counts = defaultdict(int)
            char_widths = defaultdict(float)
            
            for name, width in zip(names, lengths):
                for char in set(name):  # Use set to count unique chars
                    char_counts[char] += 1
                    char_widths[char] += width / len(name)
                    
            self.characteristic_ratios = {
                char: width / char_counts[char]
                for char, width in char_widths.items()
            }
                
        # Prepare training data
        self.X = np.array(lengths).reshape(-1, 1)
        self.y = np.array(chars)
        
        # Scale features
        self.X_scaled = self.scaler.fit_transform(self.X)
        
    def train_models(self):
        """Train both models and evaluate their performance"""
        # Train Random Forest
        rf_scores = cross_val_score(self.rf_model, self.X_scaled, self.y, cv=5)
        self.rf_model.fit(self.X_scaled, self.y)
        
        # Train Gradient Boosting
        gb_scores = cross_val_score(self.gb_model, self.X_scaled, self.y, cv=5)
        self.gb_model.fit(self.X_scaled, self.y)
        
        # Store model weights based on CV performance
        rf_weight = np.mean(rf_scores)
        gb_weight = np.mean(gb_scores)
        total = rf_weight + gb_weight
        
        self.model_weights = {
            'rf': rf_weight / total,
            'gb': gb_weight / total
        }
        
    def predict_length(self, pixel_width: float) -> Tuple[float, float]:
        """Predict string length with uncertainty estimate"""
        X_new = self.scaler.transform([[pixel_width]])
        
        # Get weighted predictions
        rf_pred = self.rf_model.predict(X_new)[0] * self.model_weights['rf']
        gb_pred = self.gb_model.predict(X_new)[0] * self.model_weights['gb']
        
        # Combine predictions
        prediction = rf_pred + gb_pred
        
        # Estimate uncertainty
        rf_std = np.std([tree.predict(X_new)[0] 
                        for tree in self.rf_model.estimators_])
        
        return prediction, rf_std
    
    def score_candidate(self, 
                       name: str, 
                       pixel_width: float, 
                       known_chars: Optional[List[str]] = None) -> float:
        """Score how likely a candidate name matches the target"""
        predicted_len, uncertainty = self.predict_length(pixel_width)
        
        # Initialize score components
        scores = []
        
        # 1. Length score using normal distribution
        length_score = norm.pdf(len(name), predicted_len, uncertainty)
        scores.append(length_score * 0.4)  # 40% weight
        
        # 2. Character density score
        density = pixel_width / len(name)
        density_score = self.density_analyzer.get_density_probability(
            len(name), 
            density
        )
        scores.append(density_score * 0.3)  # 30% weight
        
        # 3. Character composition score
        if self.characteristic_ratios:
            expected_width = sum(self.characteristic_ratios.get(c, 
                                                              density) 
                               for c in name)
            composition_score = norm.pdf(pixel_width, 
                                      expected_width, 
                                      uncertainty * len(name))
            scores.append(composition_score * 0.2)  # 20% weight
            
        # 4. Known characters match score
        if known_chars:
            match_score = sum(c in name for c in known_chars) / len(known_chars)
            scores.append(match_score * 0.1)  # 10% weight
            
        return sum(scores)
    
    def predict_words(self,
                     pixel_width: float,
                     candidates: List[str],
                     known_chars: Optional[List[str]] = None,
                     top_n: int = 5) -> List[Tuple[str, float]]:
        """Predict most likely words given pixel width and candidates"""
        # Score all candidates
        scored_candidates = [
            (name, self.score_candidate(name, pixel_width, known_chars))
            for name in candidates
        ]
        
        # Sort by score and return top N
        return sorted(scored_candidates, 
                     key=lambda x: x[1], 
                     reverse=True)[:top_n]

def main():
    # Example usage
    chars = [9,9,5,8,8,10,10,7,12,8]
    lengths = [129.9, 176.1, 89.4, 142, 132, 136, 185.2, 113.8, 224, 130]
    names = ['Holowki', 'Kresowa', 'Mila', 'Narozna', 'Parkowa', 
             'Poleska', 'Rzeczna', 'Szkolna', 'Wiejska', 'Zielona']
    
    # Initialize predictor
    predictor = EnhancedStringPredictor()
    
    # Add training data and train models
    predictor.add_training_data(chars, lengths, names)
    predictor.train_models()
    
    # Example street names to predict from
    candidates = [
        'Hołówki', 'Kresowa', 'Miodowa', 'Niecala', 'Narozna',
        'Parkowa', 'Poleska', 'Rzeczna', 'Soborny', 'Soborna',
        'Szeroka', 'Szkolna', 'Wiejska', 'Wygonna', 'Wspolna',
        'Zielona', 'Zórawia'
    ]
    
    # Make prediction
    target_width = 119
    predictions = predictor.predict_words(
        pixel_width=target_width,
        candidates=candidates,
        known_chars=['a', 'r'],  # Example known characters
        top_n=5
    )
    
    print("\nTop 5 predictions for width", target_width)
    for name, score in predictions:
        print(f"{name}: {score:.4f}")

if __name__ == "__main__":
    main()