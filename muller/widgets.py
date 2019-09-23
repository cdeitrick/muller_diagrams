import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas

NUMERIC_REGEX = re.compile("^.?(?P<number>[\d]+)")


def get_numeric_columns(columns: List[str]) -> List[str]:
	numeric_columns = list()
	for column in columns:
		if isinstance(column, str):
			match = NUMERIC_REGEX.search(column)
			if match:
				col = match.groupdict()['number']
			else:
				continue
		else:
			col = column

		try:
			int(col)
		except (ValueError, TypeError):
			continue
		numeric_columns.append(column)
	return numeric_columns


def map_trajectories_to_genotype(genotype_members: pandas.Series) -> Dict[str, str]:
	""" Maps each trajectory to the genotype it belongs to."""
	trajectory_to_genotype = dict()
	for genotype_label, members in genotype_members.items():
		for member in members.split('|'):
			trajectory_to_genotype[member] = genotype_label
	return trajectory_to_genotype


def get_valid_points(left_trajectory: pandas.Series, right_trajectory: pandas.Series, dlimit: float, flimit: Optional[float] = None,
		inner: bool = False) -> Tuple[pandas.Series, pandas.Series]:
	"""
		Filters out timepoints that do not satisfy the detection criteria.
	Parameters
	----------
	left_trajectory: pandas.Series
	right_trajectory: pandas.Series
	dlimit: float
		Removes the timepoint if both points do no exceed this value.
	flimit: float
		If given, all points exceeding this value are treated as "undetected".
	inner: bool; default False
		If `true`, both points must exceed the detection limit for a given timepoint to be considered valid.

	Returns
	-------

	"""

	if flimit is not None:
		# Mask the values so they are considered below the detection limit.
		# Assign a value of -1 so that they will be excluded even if the detection limit is 0.
		# list comprehension is ~6X faster than mask()
		left = pandas.Series([(-1 if s > 0.97 else s) for s in left_trajectory.values], index = left_trajectory.index)
		right = pandas.Series([(-1 if s > 0.97 else s) for s in right_trajectory.values], index = right_trajectory.index)
	else:
		left, right = left_trajectory, right_trajectory

	if inner:
		# list comprehensions are ~10X faster than using the built-in pandas methods.
		at_least_one_detected = [(l > dlimit and r > dlimit) for l, r in zip(left.values, right.values)]
	else:
		at_least_one_detected = [(l > dlimit or r > dlimit) for l, r in zip(left.values, right.values)]
	at_least_one_detected = pandas.Series(at_least_one_detected, index = left.index)

	# Remove indicies where the series value falls below the detection limit. This should include the masked fixed values.
	at_least_one_detected_reduced = at_least_one_detected[at_least_one_detected]
	if at_least_one_detected_reduced.empty:
		# There are no shared timepoints between the series. Assign index_min and index_max to the same number, which will result in an empty dataframe.
		position_index_min = position_index_max = 0
	else:
		# Apparently the min() and max functions now work with strings as well as numbers.
		# Cast the numbers to float so the typeerror is thrown correctly.
		try:
			position_index_min_value = min(at_least_one_detected_reduced.index, key = lambda s: float(s))
			position_index_max_value = max(at_least_one_detected_reduced.index, key = lambda s: float(s))
		except TypeError:
			# The indicies are str and we can't use min() or max(). Assume the indicies are already sorted.
			position_index_min_value = at_least_one_detected_reduced.index[0]
			position_index_max_value = at_least_one_detected_reduced.index[-1]

		position_index_min = left.index.get_loc(position_index_min_value)
		position_index_max = left.index.get_loc(position_index_max_value)
		# Since we want to include the last index, increment position_index_max by one.
		position_index_max += 1
	result_left = left_trajectory[position_index_min:position_index_max]
	result_right = right_trajectory[position_index_min:position_index_max]

	return result_left, result_right


get_detected_points = get_valid_points


def calculate_luminance(color: str) -> float:
	# 0.299 * color.R + 0.587 * color.G + 0.114 * color.B
	red = int(color[1:3], 16)
	green = int(color[3:5], 16)
	blue = int(color[5:], 16)

	lum = (.299 * red) + (.587 * green) + (.114 * blue)
	return lum / 255


def format_inconsistency_matrix(inconsistency_matrix) -> pandas.DataFrame:
	inconsistency_table = pandas.DataFrame(inconsistency_matrix, columns = ['mean', 'std', 'observations', 'statistic'])
	inconsistency_table['observations'] = inconsistency_table['observations'].astype(int)
	return inconsistency_table


# noinspection PyTypeChecker,PyUnresolvedReferences
def fixed_immediately(trajectory: pandas.Series, dlimit: float, flimit: float) -> bool:
	mask1 = (trajectory <= dlimit)
	mask2 = (trajectory >= flimit)
	return (mask1.sum() + mask2.sum()) == len(trajectory)


def fixed(trajectory: pandas.Series, flimit: float) -> bool:
	""" Tests whether the input series fixed at any point."""
	return any(i > flimit for i in trajectory.values)


def only_fixed(trajectory: pandas.Series, dlimit: float, flimit: float) -> bool:
	""" Tests whether the series immediately fixed and stayed fixed."""
	series = ((i > flimit or i < dlimit) for i in trajectory.values)
	return all(series)


def overlap(left: pandas.Series, right: pandas.Series, dlimit: float) -> int:
	result = [(i > dlimit and j > dlimit) for i, j in zip(left.values, right.values)]

	return sum(result)


def find_boundaries_detected(trajectory: pandas.Series, dlimit: float) -> Tuple[int, int]:
	""" Returns the start and stop points of a series"""
	detected = trajectory[trajectory > dlimit]
	return min(detected.index), max(detected.index)


def find_boundaries_fixed(trajectory: pandas.Series, flimit: float) -> Optional[Tuple[int, int]]:
	fixed_series = trajectory[trajectory > flimit]
	# Assume index is sorted to avoid the situation where the index is str.
	if fixed_series.empty: return None
	else:
		return fixed_series.index[0], fixed_series.index[-1]


def _get_git_log() -> str:
	filename = Path(__file__).parent.parent / ".git" / "logs" / "HEAD"
	try:
		contents = filename.read_text()
	except FileNotFoundError:
		contents = ""
	return contents


def get_commit_hash() -> str:
	commit_hash = "n/a"
	contents = _get_git_log()
	if contents:
		contents = contents.split('\n')
		contents = [i.strip() for i in contents if i.strip()]
		reader = csv.reader(contents, delimiter = '\t')
		for line in reader:
			if line:
				hash_string = line[0]
				try:
					commit_hash = hash_string.split()[1]
				except IndexError:
					continue
		commit_hash = commit_hash[:7]
	else:
		commit_hash = "not available"
	return commit_hash
