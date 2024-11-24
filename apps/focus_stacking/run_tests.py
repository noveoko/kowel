# run_tests.py
import unittest
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Load tests
loader = unittest.TestLoader()
start_dir = "tests"
suite = loader.discover(start_dir, pattern="test_*.py")

# Run tests
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Exit with appropriate code
sys.exit(not result.wasSuccessful())
