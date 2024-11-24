from setuptools import setup, find_packages

setup(
    name="focus_stacking",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "Pillow>=10.0.0",
        "typing-extensions>=4.0.0",
    ],
)
