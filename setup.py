from setuptools import setup, find_packages

from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.org")) as f:
    long_desc = f.read()

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="A-Compiler",
    version="0.1.0",
    description="My Compiler",
    author="ben simms",
    packages=find_packages(exclude=("examples", "tests")),
    install_requires=requirements,
    package_data={"": ["*.ebnf"]},
    entry_points={
        "console_scripts": [
            "wewcompile=compiler.backend.rustvm:compile"
        ]
    }
)
