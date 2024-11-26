import numpy as np
import subprocess
import cv2
from deap import base, creator, tools, algorithms
import random
import multiprocessing
from pathlib import Path
import json
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr
import logging
from datetime import datetime

class EnfuseParameterOptimizer:
    def __init__(self, input_images, reference_image=None, population_size=50, generations=30):
        """
        Initialize the genetic optimizer for Enfuse parameters.
        
        Args:
            input_images: List of paths to input images
            reference_image: Optional high-quality reference image for comparison
            population_size: Size of the genetic population
            generations: Number of generations to evolve
        """
        self.input_images = [Path(img) for img in input_images]
        self.reference_image = Path(reference_image) if reference_image else None
        self.population_size = population_size
        self.generations = generations
        self.work_dir = Path("enfuse_optimization")
        self.work_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
        # Parameter ranges for genetic optimization
        self.param_ranges = {
            "exposure-weight": (0.0, 1.0),
            "saturation-weight": (0.0, 1.0),
            "contrast-weight": (0.0, 1.0),
            "contrast-window": (3, 15),
            "contrast-edge-scale": (0.0, 1.0),
            "contrast-min-curvature": (0.0, 1.0),
            "hard-mask": (0, 1),  # Boolean
            "gray-projector": (0, 2),  # Discrete choices: average, value, lightness
            "opacity": (0.0, 1.0)
        }
        
        # Initialize genetic programming tools
        self.setup_genetic_tools()
        
    def setup_logging(self):
        """Configure logging for the optimization process"""
        logging.basicConfig(
            filename=f'enfuse_optimization_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_genetic_tools(self):
        """Initialize DEAP genetic programming tools"""
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        creator.create("Individual", list, fitness=creator.FitnessMax)
        
        self.toolbox = base.Toolbox()
        
        # Register parameter generators
        for param_name, (min_val, max_val) in self.param_ranges.items():
            if isinstance(min_val, int) and isinstance(max_val, int):
                self.toolbox.register(
                    f"rand_{param_name.replace('-', '_')}", 
                    random.randint, min_val, max_val
                )
            else:
                self.toolbox.register(
                    f"rand_{param_name.replace('-', '_')}", 
                    random.uniform, min_val, max_val
                )
        
        # Register individual and population generators
        self.toolbox.register(
            "individual",
            tools.initCycle,
            creator.Individual,
            [getattr(self.toolbox, f"rand_{param.replace('-', '_')}") 
             for param in self.param_ranges.keys()],
            n=1
        )
        
        self.toolbox.register(
            "population",
            tools.initRepeat,
            list,
            self.toolbox.individual,
            n=self.population_size
        )
        
        # Register genetic operators
        self.toolbox.register("evaluate", self.evaluate_parameters)
        self.toolbox.register("mate", tools.cxTwoPoint)
        self.toolbox.register("mutate", self.custom_mutate)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
        
    def custom_mutate(self, individual):
        """Custom mutation operator that respects parameter ranges"""
        for i, (param_name, (min_val, max_val)) in enumerate(self.param_ranges.items()):
            if random.random() < 0.1:  # 10% mutation rate per parameter
                if isinstance(min_val, int) and isinstance(max_val, int):
                    individual[i] = random.randint(min_val, max_val)
                else:
                    individual[i] = random.uniform(min_val, max_val)
        return individual,
    
    def parameters_to_command(self, parameters):
        """Convert parameter list to enfuse command"""
        cmd = ["enfuse"]
        
        for param_name, value in zip(self.param_ranges.keys(), parameters):
            if param_name == "hard-mask":
                if value > 0.5:
                    cmd.append("--hard-mask")
            elif param_name == "gray-projector":
                projector_types = ["average", "value", "lightness"]
                cmd.extend([f"--gray-projector={projector_types[int(value % 3)]}"])
            else:
                cmd.extend([f"--{param_name}={value:.3f}"])
        
        return cmd
    
    def evaluate_parameters(self, parameters):
        """Evaluate a set of enfuse parameters"""
        try:
            # Create unique output path for this evaluation
            output_path = self.work_dir / f"result_{hash(tuple(parameters))}.tiff"
            
            # Build and run enfuse command
            cmd = self.parameters_to_command(parameters)
            cmd.extend(["-o", str(output_path)])
            cmd.extend([str(img) for img in self.input_images])
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Evaluate result
            score = self.calculate_image_quality(output_path)
            
            # Cleanup
            output_path.unlink()
            
            return (score,)
            
        except Exception as e:
            self.logger.error(f"Error evaluating parameters: {e}")
            return (-float('inf'),)
    
    def calculate_image_quality(self, result_path):
        """Calculate quality metrics for the result image"""
        result_img = cv2.imread(str(result_path))
        
        if self.reference_image is not None:
            # Compare with reference image if available
            ref_img = cv2.imread(str(self.reference_image))
            ssim_score = ssim(result_img, ref_img, multichannel=True)
            psnr_score = psnr(result_img, ref_img)
            return (ssim_score + psnr_score / 100) / 2
        else:
            # Calculate intrinsic quality metrics
            gray = cv2.cvtColor(result_img, cv2.COLOR_BGR2GRAY)
            
            # Laplacian variance (sharpness)
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Local contrast
            local_contrast = np.std(gray)
            
            # Normalize and combine metrics
            return (np.log(lap_var + 1) + local_contrast / 255) / 2
    
    def optimize(self):
        """Run the genetic optimization process"""
        self.logger.info("Starting optimization")
        
        # Enable parallel processing
        pool = multiprocessing.Pool()
        self.toolbox.register("map", pool.map)
        
        # Initialize population
        pop = self.toolbox.population()
        hof = tools.HallOfFame(1)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("min", np.min)
        stats.register("max", np.max)
        
        # Run evolution
        pop, logbook = algorithms.eaSimple(
            pop, self.toolbox,
            cxpb=0.7,  # Crossover probability
            mutpb=0.2,  # Mutation probability
            ngen=self.generations,
            stats=stats,
            halloffame=hof,
            verbose=True
        )
        
        pool.close()
        
        # Get best parameters
        best_params = dict(zip(self.param_ranges.keys(), hof[0]))
        
        # Save best parameters
        with open("best_enfuse_params.json", "w") as f:
            json.dump(best_params, f, indent=4)
        
        self.logger.info(f"Optimization complete. Best parameters: {best_params}")
        return best_params, logbook

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Optimize Enfuse parameters using genetic programming")
    parser.add_argument("input_dir", help="Directory containing input images")
    parser.add_argument("--reference", help="Optional reference image")
    parser.add_argument("--generations", type=int, default=30, help="Number of generations")
    parser.add_argument("--population", type=int, default=50, help="Population size")
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    input_images = list(input_dir.glob("*.tif")) + list(input_dir.glob("*.tiff"))
    
    optimizer = EnfuseParameterOptimizer(
        input_images=input_images,
        reference_image=args.reference,
        population_size=args.population,
        generations=args.generations
    )
    
    best_params, logbook = optimizer.optimize()
    print("Optimization complete!")
    print("\nBest parameters:")
    for param, value in best_params.items():
        print(f"{param}: {value}")

if __name__ == "__main__":
    main()