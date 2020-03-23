from setuptools import setup
from muller import commandline_parser
from pathlib import Path
if commandline_parser.DEBUG:
	message = "The scripts are currently in debug mode!"
	raise ValueError(message)
FOLDER = Path(__file__).parent
README = FOLDER / "README.md"

with README.open() as readmefile:
	LONG_DESCRIPTION = readmefile.read()

setup(
	name = 'lolipop',
	version = commandline_parser.__VERSION__,
	packages = [
		'muller', 'muller.clustering', 'muller.dataio', 'muller.graphics', 'muller.inheritance',
		'muller.graphics.palettes', 'muller.clustering.metrics', 'muller.workflows',
		'muller.utilities'
	],
	extras_require = {
		'Additional support for parsing files': ['beautifulsoup4'],
		'List similar annotations when selecting genotypes': ['rapidfuzz'],
		'Generate composite graphs from the genotye/lineage/timeseries plots': ["pillow"],
		'To run tests': ["pytest"]
	},
	provides = 'lolipop',
	url = 'https://github.com/cdeitrick/lolipop',
	license = 'MIT',
	author = 'chris deitrick',
	author_email = 'chrisdeitrick1@gmail.com',
	description = 'A set of scripts to cluster mutational trajectories into genotypes and infer lineage in the context of population evolution experiments.',
	long_description = LONG_DESCRIPTION,
	long_description_content_type='text/markdown',
	install_requires = [
		'pandas>=0.24.0', 'loguru', 'scipy>=1.3.0', 'matplotlib>=3.0.0','graphviz',
		'pygraphviz', 'seaborn', 'numpy>=1.16.2', 'xlrd', 'shapely>=1.6.4', 'tqdm'
	],
	tests_requires = ['pytest'],
	classifiers = [
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: MIT License",
		"Operating System :: OS Independent",
	],
	scripts = ["lolipop"]
)
