import logging
import random
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas
from dataclasses import dataclass

#logging.basicConfig(level = logging.INFO, format = '%(asctime)s - %(levelname)s - %(message)s')
#logger = logging.getLogger(__name__)

OutputType = Tuple[pandas.DataFrame, pandas.DataFrame, str, Dict[str, Any]]
try:
	import yaml
except ModuleNotFoundError:
	yaml = None

try:
	from muller.calculate_genotypes import GenotypeOptions
	from muller.sort_genotypes import SortOptions
	from muller.order_clusters import OrderClusterParameters, ClusterType
	from muller.genotype_plots import plot_genotypes
	from muller.generate_muller_plot import generate_muller_plot
	from muller.r_integration import generate_ggmuller_script
except ModuleNotFoundError:
	from calculate_genotypes import GenotypeOptions, PairwiseArrayType
	from sort_genotypes import SortOptions
	from order_clusters import OrderClusterParameters, ClusterType
	from genotype_plots import plot_genotypes
	from generate_muller_plot import generate_muller_plot
	from r_integration import generate_ggmuller_script


@dataclass
class WorkflowData:
	filename: Path
	info: Optional[pandas.DataFrame]
	original_trajectories: Optional[pandas.DataFrame]
	original_genotypes: Optional[pandas.DataFrame]
	trajectories: pandas.DataFrame
	genotypes: pandas.DataFrame
	clusters: ClusterType
	genotype_options: GenotypeOptions
	sort_options: SortOptions
	cluster_options: OrderClusterParameters
	p_values: PairwiseArrayType


DETECTION_CUTOFF = 0.03


def convert_population_to_ggmuller_format(mean_genotypes: pandas.DataFrame, edges: pandas.DataFrame) -> pandas.DataFrame:
	"""
		Converts the genotype frequencies to a population table suitable for ggmuller.
	Parameters
	----------
	mean_genotypes: pandas.DataFrame
	edges: pandas.DataFrame
		The output from create_ggmuller_edges()
	fixed_cutoff: float
		The cutoff used to identify if/when a genotype fixes.

	Returns
	-------

	"""

	# "Generation", "Identity" and "Population"
	# Adjust populations to account for inheritance.
	# If a child genotype fixed, the parent genotype should be replaced.

	# Use a copy of the dataframe to avoid making changes to the original.
	modified_genotypes: pandas.DataFrame = mean_genotypes.copy(True)
	modified_genotypes.pop('members')

	# Generate a list of all genotypes that arise in the background of each genotype.
	children = dict()
	for _, row in edges.iterrows():
		parent = row['Parent']
		identity = row['Identity']

		children[parent] = children.get(parent, list()) + [identity]

	table = list()

	for genotype_label, genotype in modified_genotypes.iterrows():
		if genotype_label in children:
			genotype_frequencies = genotype[genotype > DETECTION_CUTOFF]
			genotype_children: pandas.Series = modified_genotypes.loc[children[genotype_label]].max()
			genotype_frequencies: pandas.Series = genotype_frequencies - genotype_children
			genotype_frequencies = genotype_frequencies.mask(lambda s: s < DETECTION_CUTOFF, 0.01)
			genotype_frequencies = genotype_frequencies.dropna()

		else:
			genotype_frequencies = genotype

		# Remove timepoints where the value was 0 or less than 0 due to above line.

		for timepoint, frequency in genotype_frequencies.items():
			row = {
				'Identity':   genotype_label,
				'Generation': timepoint,
				'Population': frequency * 100
			}
			table.append(row)
	# table.append({'Generation': 0, "Identity": "genotype-0", "Population": 100})
	temp_df = pandas.DataFrame(table)

	generation_groups = temp_df.groupby(by = 'Generation')
	for generation, group in generation_groups:
		population = group['Population'].sum()
		if population <= 100:
			p = 100 - population
		else:
			p = 0
		table.append({'Generation': generation, "Identity": "genotype-0", "Population": p})

	return pandas.DataFrame(table)


def create_ggmuller_edges(genotype_clusters: ClusterType) -> pandas.DataFrame:
	table = list()
	for genotype_info in genotype_clusters.values():
		identity = genotype_info.name
		background = genotype_info.background

		if len(background) == 1:
			parent = 'genotype-0'
		else:
			parent = background[0]
		if parent == identity:
			parent = 'genotype-0'

		row = {
			'Parent':   parent,
			'Identity': identity
		}
		table.append(row)
	table = pandas.DataFrame(table)[['Parent', 'Identity']]

	return table


def generate_formatted_output(workflow_data: WorkflowData, color_palette: Dict[str, str]) -> OutputType:
	"""
		Generates the final output files for the population.
	Parameters
	----------
	workflow_data: WorkflowData
		The data generated by the workflow.
	color_palette: Dict[str, str]
		A map dictating the color of each genotype.
	fixed_cutoff: float
		The cutoff to indicate if/when a genotype has fixed.

	Returns
	-------
	Tuple[pandas.DataFrame, Dict[str,Any], pandas.DataFrame, Dict[str,float], str, pandas.DataFrame, pandas.DataFrame]
	"""

	workflow_parameters = get_workflow_parameters(workflow_data)
	#logger.info("generating edges...")
	ggmuller_edge_table = create_ggmuller_edges(workflow_data.clusters)
	#logger.info("generating populations...")
	ggmuller_population_table = convert_population_to_ggmuller_format(workflow_data.genotypes, ggmuller_edge_table)

	#logger.info("generating mermaid diagram...")
	mermaid_diagram = generate_mermaid_diagram(ggmuller_edge_table, color_palette)
	#logger.info("generating trajectories table...")
	if workflow_data.info is not None:
		genotype_map = {k: v.split('|') for k, v in workflow_data.genotypes['members'].items()}
		trajectory_map = dict()
		for g, v in genotype_map.items():
			for t in v:
				trajectory_map[t] = g
		trajectory_table: pandas.DataFrame = workflow_data.trajectories.copy()

		trajectory_table['genotype'] = [trajectory_map[k] for k in trajectory_table.index]
		trajectory_table = trajectory_table.join(workflow_data.info).sort_values(by = ['genotype'])
		workflow_data.trajectories = trajectory_table

	return ggmuller_population_table, ggmuller_edge_table, mermaid_diagram, workflow_parameters


def generate_mermaid_diagram(backgrounds: pandas.DataFrame, color_palette: Dict[str, str]) -> str:
	"""
	graph LR
    id1(Start)-->id2(Stop)
    style id1 fill:#f9f,stroke:#333,stroke-width:4px
    style id2 fill:#ccf,stroke:#f66,stroke-width:2px,stroke-dasharray: 5, 5
	Parameters
	----------
	backgrounds
	color_palette

	Returns
	-------

	"""
	genotype_labels = list(set(backgrounds['Identity'].values))

	node_map = {k: "style id{} fill:{}".format(k.split('-')[-1], color_palette[k]) for k in genotype_labels}

	diagram_contents = ["graph TD;"]
	for _, row in backgrounds.iterrows():
		parent = row['Parent']
		identity = row['Identity']
		parent_id = parent.split('-')[-1]
		identity_id = identity.split('-')[-1]
		line = "id{left_id}({left})-->id{right_id}({right});".format(
			left_id = identity_id,
			right_id = parent_id,
			left = identity,
			right = parent
		)
		diagram_contents.append(line)

	diagram_contents += list(node_map.values())

	return "\n".join(diagram_contents)


def generate_output(workflow_data: WorkflowData, output_folder: Path, fixed_cutoff: float, annotate_all: bool):
	color_palette = [
		'#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
		'#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe',
		'#008080', '#e6beff', '#9a6324', '#fffac8', '#800000',
		'#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080',
		'#ffffff', '#000000'
	]

	if len(workflow_data.original_genotypes) >= len(color_palette):
		color_palette += [generate_random_color() for _ in workflow_data.genotypes.index]

	color_map = {i: j for i, j in zip(sorted(workflow_data.genotypes.index), color_palette)}
	color_map['genotype-0'] = "#333333"

	population, edges, mermaid, parameters = generate_formatted_output(workflow_data, color_map)
	save_output(workflow_data, population, edges, mermaid, parameters, output_folder, color_map, annotate_all)


def generate_random_color() -> str:
	r = random.randint(50, 200)
	g = random.randint(50, 200)
	b = random.randint(50, 200)
	color = "#{:>02X}{:>02X}{:>02X}".format(r, g, b)
	return color


def get_numeric_columns(columns: List) -> List[Union[int, float]]:
	output_columns = list()
	for col in columns:
		try:
			int(col)
			output_columns.append(col)
		except ValueError:
			pass
	return output_columns


def get_workflow_parameters(workflow_data: WorkflowData) -> Dict[str, float]:
	parameters = {
		# get_genotype_options
		'detectionCutoff':                        workflow_data.genotype_options.detection_breakpoint,
		'fixedCutoff':                            workflow_data.genotype_options.fixed_breakpoint,
		'similarityCutoff':                       workflow_data.genotype_options.similarity_breakpoint,
		'differenceCutoff':                       workflow_data.genotype_options.difference_breakpoint,
		# sort options
		'significanceCutoff':                     workflow_data.sort_options.significant_breakpoint,
		'frequencyCutoffs':                       workflow_data.sort_options.frequency_breakpoints,
		# cluster options
		'additiveBackgroundDoubleCheckCutoff':    workflow_data.cluster_options.additive_background_double_cutoff,
		'additiveBackgroundSingleCheckCutoff':    workflow_data.cluster_options.additive_background_single_cutoff,
		'subtractiveBackgroundDoubleCheckCutoff': workflow_data.cluster_options.subtractive_background_double_cutoff,
		'subtractiveBackgroundSingleCheckCutoff': workflow_data.cluster_options.subtractive_background_single_cutoff,
		'derivativeDetectionCutoff':              workflow_data.cluster_options.derivative_detection_cutoff,
		'derivativeCheckCutoff':                  workflow_data.cluster_options.derivative_check_cutoff
	}
	return parameters


def save_output(workflow_data: WorkflowData, population_table: pandas.DataFrame, edge_table: pandas.DataFrame,
		mermaid_diagram: str, parameters: Dict, output_folder: Path, color_palette: Dict[str, str], annotate_all: bool):
	name = workflow_data.filename.stem
	delimiter = '\t'
	subfolder = output_folder / "supplementary-files"
	if not subfolder.exists():
		subfolder.mkdir()

	trajectory_to_genotype = dict()
	for label, genotype in workflow_data.genotypes.iterrows():
		items = genotype['members'].split('|')
		for i in items:
			trajectory_to_genotype[i] = label

	original_trajectory_file = subfolder / (name + '.trajectories.original.tsv')
	trajectory_output_file = output_folder / (name + '.trajectories.tsv')

	original_genotype_file = subfolder / (name + '.genotypes.original.tsv')
	genotype_output_file = output_folder / (name + '.genotypes.tsv')

	population_output_file = output_folder / (name + '.ggmuller.populations.tsv')
	edges_output_file = output_folder / (name + '.ggmuller.edges.tsv')

	r_script_file = subfolder / (name + '.r')
	muller_table_file = subfolder / (name + '.muller.tsv')
	muller_plot_basic_file = output_folder / (name + '.muller.basic.png')
	muller_plot_annotated_file = output_folder / (name + '.muller.annotated.png')

	mermaid_diagram_script = subfolder / (name + '.mermaid.md')
	mermaid_diagram_render = output_folder / (name + '.mermaid.png')

	# original_genotype_plot_filename = subfolder / (name + '.original.png')
	genotype_plot_filename = output_folder / (name + '.filtered.png')
	p_value_filename = subfolder / (name + ".pvalues.yaml")

	with p_value_filename.open('w') as pfile:
		for (l, r), v in sorted(workflow_data.p_values.items()):
			pfile.write(f"{l}\t{r}\t{v}\n")

	population_table.to_csv(str(population_output_file), sep = delimiter, index = False)
	edge_table.to_csv(str(edges_output_file), sep = delimiter, index = False)

	workflow_data.original_genotypes.to_csv(str(original_genotype_file), sep = delimiter)
	workflow_data.genotypes.to_csv(str(genotype_output_file), sep = delimiter)

	if workflow_data.original_trajectories is not None:
		workflow_data.original_trajectories.to_csv(str(original_trajectory_file), sep = delimiter)

	if workflow_data.trajectories is not None:
		workflow_data.trajectories['genotype'] = [trajectory_to_genotype[i] for i in workflow_data.trajectories.index]
		workflow_data.trajectories.to_csv(str(trajectory_output_file), sep = delimiter)

	#logger.info("Plotting trajectories")
	# plot_genotypes(workflow_data.original_trajectories, workflow_data.original_genotypes, original_genotype_plot_filename, color_palette)
	plot_genotypes(workflow_data.trajectories, workflow_data.genotypes, genotype_plot_filename, color_palette)

	mermaid_diagram_script.write_text(mermaid_diagram)
	try:
		subprocess.call(
			["mmdc", "--height", "400", "-i", mermaid_diagram_script, "-o", mermaid_diagram_render],
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE)
	except FileNotFoundError:
		pass

	#logger.info("generating r script")
	muller_df = generate_ggmuller_script(
		trajectory = trajectory_output_file,
		population = population_output_file,
		edges = edges_output_file,
		table_filename = muller_table_file,
		plot_filename = muller_plot_basic_file,
		script_filename = r_script_file,
		color_palette = color_palette
	)
	if muller_df is not None:
		generate_muller_plot(muller_df, workflow_data.trajectories, color_palette, muller_plot_annotated_file, annotate_all)

	#logger.info("generating muller plot...")
	subprocess.call(['Rscript', '--vanilla', '--silent', r_script_file], stdout = subprocess.PIPE,
		stderr = subprocess.PIPE)
	_extra_file = Path.cwd() / "Rplots.pdf"
	if _extra_file.exists():
		_extra_file.unlink()

	if yaml:
		fname = output_folder / (name + '.yaml')
		fname.write_text(yaml.dump(parameters))
	else:
		import json
		fname = output_folder / (name + '.json')
		fname.write_text(json.dumps(parameters, indent = 2))
