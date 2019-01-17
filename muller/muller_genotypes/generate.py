from typing import Any, Tuple

import pandas

try:
	from options import GenotypeOptions
	from muller_genotypes.metrics.similarity import PairCalculation
	from muller.muller_genotypes.methods import matlab_method, hierarchical_method
	from muller.muller_genotypes.average import calculate_mean_genotype
	from muller_genotypes.metrics.pairwise_calculation import PairwiseCalculation
except ModuleNotFoundError:
	from .metrics.similarity import PairCalculation
	from .methods import matlab_method, hierarchical_method
	from .average import calculate_mean_genotype
	from .metrics.pairwise_calculation import PairwiseCalculation

PAIRWISE_CALCULATIONS = PairwiseCalculation()


def generate_genotypes(timepoints: pandas.DataFrame, options: GenotypeOptions) -> Tuple[pandas.DataFrame, pandas.Series, Any]:
	"""

	Parameters
	----------
	timepoints: pandas.DataFrame
		A timeseries dataframe, usually generated from `import_table.import_trajectory_table`.
			- Index -> str
				Names unique to each trajectory.
			- Columns -> int
				The timeseries points will correspond to the frequencies for each trajectory included with the input sheet.
				Each trajectory/timepoint will include the observed frequency at each timepoint.
	options: GenotypeOptions
		An instance of `GenotypeOptions` with the desired options. Can be generated automatically via `GenotypeOptions.from_breakpoints(0.03)`.

	Returns
	-------
	pandas.DataFrame, pandas.Series
		- The genotype table
		- A map of genotypes to members.
	"""
	# calculate the similarity between all pairs of trajectories in the population.
	PAIRWISE_CALCULATIONS.update_values(timepoints, options.detection_breakpoint, options.fixed_breakpoint)

	if options.method == "matlab":
		genotypes = matlab_method(timepoints, PAIRWISE_CALCULATIONS, options.similarity_breakpoint, options.difference_breakpoint, options.starting_genotypes)
		linkage_matrix = None
	elif options.method == "hierarchy":
		genotypes, linkage_matrix = hierarchical_method(PAIRWISE_CALCULATIONS, options.similarity_breakpoint)
	else:
		raise ValueError(f"Invalid clustering method: {options.method}")

	_mean_genotypes = calculate_mean_genotype(genotypes, timepoints)
	genotype_members = _mean_genotypes.pop('members')
	_mean_genotypes = _mean_genotypes[sorted(_mean_genotypes.columns)]

	return _mean_genotypes, genotype_members, linkage_matrix


if __name__ == "__main__":
	pass
