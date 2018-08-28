
import pandas

pandas.set_option('display.max_columns', 400)
pandas.set_option('display.width', 400)
from typing import List
from dataclasses import dataclass

@dataclass
class SortOptions:
	detection_breakpoint: float
	significant_breakpoint: float
	fixed_breakpoint: float
	frequency_breakpoints: List[float]  # Used when sorting non-fixed genotypes.

	@classmethod
	def from_matlab(cls) -> 'SortOptions':
		return SortOptions(
			detection_breakpoint = 0.03,
			significant_breakpoint = 0.15,
			fixed_breakpoint = 0.85,
			frequency_breakpoints = [0.90, 0.75, 0.60, 0.45, 0.30, 0.15, 0.00]
		)


def sort_genotypes(genotype_frequencies: pandas.DataFrame, options: SortOptions) -> pandas.DataFrame:
	"""
		Sorts the genotypes based on when they were first detected and first fixed.
	Parameters
	----------
	genotype_frequencies:pandas.Dataframe
		A dataframe with the mean frequency of each genotype, derived from the member trajectories
		in that genotype. Each row should correspond to a single genotype.
	options: SortOptions

	Returns
	-------
	sorted_genotype: pandas.DataFrame
	"""
	# sorted_dataframe = sort_genotype_frequencies(genotype_frequencies, FIXED_THRESHOLD)
	sorted_genotypes = list()
	current_genotypes: pandas.DataFrame = genotype_frequencies.copy()
	if 'members' in current_genotypes:
		current_genotypes.pop('members')
	for frequency in [options.fixed_breakpoint] + options.frequency_breakpoints:
		sorted_dataframe = sort_genotype_frequencies(
			genotype_trajectories = current_genotypes,
			frequency_breakpoint = frequency,
			detection_cutoff = options.detection_breakpoint,
			significant_cutuff = options.significant_breakpoint,
			fixed_cutoff = options.fixed_breakpoint
		)
		if not sorted_dataframe.empty:
			current_genotypes = current_genotypes.drop(sorted_dataframe.index)
			sorted_genotypes.append(sorted_dataframe)

	df = pandas.concat(sorted_genotypes)
	df = genotype_frequencies.reindex(df.index)
	return df


def sort_genotype_frequencies(genotype_trajectories: pandas.DataFrame, frequency_breakpoint: float,
		detection_cutoff: float, significant_cutuff: float, fixed_cutoff: float) -> pandas.DataFrame:
	# Should be 1, 7, 2|3, 6, 8|4, 5, 14, 9|17, 19|13|..., 21|10|15, 18|11
	# Should Be 8, 7|12|28,
	# frequency_threshold = FIXED_THRESHOLD if FREQUENCY_THRESHOLD < frequency_breakpoint else frequency_breakpoint

	transposed = genotype_trajectories.transpose()

	first_detected: pandas.Series = (transposed > detection_cutoff).idxmax(0).sort_values()
	first_detected.name = 'firstDetected'

	first_above_threshold: pandas.Series = (transposed > significant_cutuff).idxmax(0).sort_values()
	first_above_threshold.name = 'firstThreshold'

	# noinspection PyUnresolvedReferences
	first_fixed: pandas.Series = (transposed > frequency_breakpoint).idxmax(0).sort_values()
	first_fixed.name = 'firstFixed'

	# Remove the genotypes which were never detected or never rose above the threshold.
	first_detected_reduced = first_detected.iloc[first_detected.nonzero()]
	first_above_threshold_reduced = first_above_threshold.replace(0,
		13)  # To replicate the behavior in the matlab script
	first_fixed_reduced = first_fixed.iloc[first_fixed.nonzero()]

	df: pandas.DataFrame = pandas.concat([first_fixed_reduced, first_detected_reduced, first_above_threshold_reduced],
		axis = 1)
	df = df[~df['firstFixed'].isna()]

	if frequency_breakpoint == fixed_cutoff:
		df = df.dropna()
	sorted_frequencies = df.sort_values(by = ['firstDetected', 'firstThreshold'])

	# Sort genotypes based on frequency if two or more share the same fixed timepoint, detection timpoint, threshold timepoint.

	debug = False
	if not debug:
		freq_groups = list()
		groups = sorted_frequencies.groupby(by = list(sorted_frequencies.columns))
		for label, group in groups:
			trajectories = genotype_trajectories.loc[group.index]
			if len(group) < 2:
				freq_groups.append(trajectories)
			else:
				trajectories = genotype_trajectories.drop(
					[gt for gt in genotype_trajectories.index if gt not in group.index])
				# sgens = gens.sort_values(by = list(genotype_trajectories.columns))
				freq_groups.append(trajectories)
		if freq_groups:  # Make sure freq_groups is not empty
			freq_df = pandas.concat(freq_groups)
		else:
			freq_df = sorted_frequencies
	else:
		freq_df = sorted_frequencies
	return freq_df


def workflow(mean_genotypes: pandas.DataFrame, options: SortOptions = None, matlab:bool=False, detection_cutoff: float = 0.03,
		fixed_cutoff: float = None, significant_cutoff: float = 0.15, frequency_breakpoint: float = None):
	if matlab:
		options = SortOptions.from_matlab()
	if not options:
		if frequency_breakpoint is None:
			frequency_breakpoint = [0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30, 0.20, 0.10, 0.00]
		else:
			frequency_breakpoint = [frequency_breakpoint*i for i in range(int(1/frequency_breakpoint)+1)]
		if fixed_cutoff is None:
			fixed_cutoff = 1 - detection_cutoff
		options = SortOptions(
			detection_breakpoint = detection_cutoff,
			fixed_breakpoint = fixed_cutoff,
			significant_breakpoint = significant_cutoff,
			frequency_breakpoints = frequency_breakpoint
		)
	sorted_genotypes = sort_genotypes(mean_genotypes, options)

	return sorted_genotypes


if __name__ == "__main__":
	pass
