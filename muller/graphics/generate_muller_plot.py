"""
	Python implementation of the Muller_plot function available from ggmuller.
"""
import logging
import math
import random
from itertools import filterfalse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas
from matplotlib import pyplot as plt
# plt.switch_backend('agg')
from matplotlib.figure import Axes  # For autocomplete

logger = logging.getLogger(__file__)
plt.style.use('seaborn-white')

pandas.set_option('display.max_rows', 500)
pandas.set_option('display.max_columns', 500)
pandas.set_option('display.width', 250)


def unique_everseen(iterable, key = None):
	"""	List unique elements, preserving order. Remember all elements ever seen."
		unique_everseen('AAAABBBCCDAABBB') --> A B C D
		unique_everseen('ABBCcAD', str.lower) --> A B C D
	"""
	seen = set()
	seen_add = seen.add
	if key is None:
		for element in filterfalse(seen.__contains__, iterable):
			seen_add(element)
			yield element
	else:
		for element in iterable:
			k = key(element)
			if k not in seen:
				seen_add(k)
				yield element


def generate_muller_series(muller_df: pandas.DataFrame, color_palette: Dict[str, str]) -> Tuple[List[float], List[List[float]], List[str], List[str]]:
	"""
		Generates the required inputs for matplotlib to generate a mullerplot.
	Parameters
	----------
	muller_df: pandas.DataFrame
	color_palette: Dict[str,str]
		Maps genotypes to a specific color.

	Returns
	-------
	x, y, colors, labels
	"""
	genotype_order = list(unique_everseen(muller_df['Group_id'].tolist()))

	x = list(unique_everseen(muller_df['Generation'].tolist()))

	colors = [color_palette[genotype_label[:-1] if genotype_label.endswith('a') else genotype_label] for genotype_label in genotype_order]
	labels = [(label if not label.endswith('a') else None) for label in genotype_order]
	groups = muller_df.groupby(by = 'Group_id')
	y = [groups.get_group(label)['Frequency'].tolist() for label in genotype_order]

	return x, y, colors, labels


def get_coordinates(muller_df: pandas.DataFrame) -> Dict[str, Tuple[int, float]]:
	"""
		Attempts to find the mean point of the stacked area plot for each genotype.
	Parameters
	----------
	muller_df:pandas.DataFrame

	Returns
	-------
	points: Dict[str, Tuple[int, float]]
	A dictionary mapping each genotype to an estimate of the midpoint of the genotype's area.
	"""
	genotype_order = list()
	for index, row in muller_df.iterrows():
		genotype_label = row['Group_id']
		if genotype_label not in genotype_order:
			genotype_order.append(genotype_label)

	nonzero = muller_df[muller_df['Population'] != 0]

	points = dict()
	groups = nonzero.groupby(by = 'Group_id')

	for index, name, in enumerate(genotype_order):
		genotype_label = name[:-1] if name.endswith('a') else name
		if genotype_label in points: continue
		try:
			group = groups.get_group(name)
		except KeyError:
			continue

		min_x = min(group['Generation'].values)
		max_x = max(group['Generation'].values)
		x = (min_x + max_x) / 2
		if x not in group['Generation'].values:
			x = sorted(group['Generation'].values, key = lambda s: s - x)[0]

		gdf = nonzero[nonzero['Group_id'].isin(genotype_order[:index] + [genotype_label])]
		# gdf = gdf[gdf['Population'] != 50]
		gdf = gdf[gdf['Generation'] == x]

		mid_y = sum(gdf['Frequency'].values)
		if mid_y < 0: mid_y = 0
		if x == 0:
			x = 0.1
		points[genotype_label] = (x, mid_y)  # + .25)

	return points


def get_font_properties(genotype_color: str) -> Dict[str, Any]:
	"""
		Generates font properties for each annotations. The main difference is font color,
		which is determined by the background color.
	Parameters
	----------
	genotype_label: str
	colormap: Dict[str,str]

	Returns
	-------
	fontproperties: Dict[str, Any]
	"""

	luminance = calculate_luminance(genotype_color)
	if luminance > 0.5:
		font_color = "#333333"
	else:
		font_color = "#FFFFFF"
	label_properties = {
		'size':  9,
		'color': font_color
	}
	return label_properties


def calculate_luminance(color: str) -> float:
	# 0.299 * color.R + 0.587 * color.G + 0.114 * color.B

	red = int(color[1:3], 16)
	green = int(color[3:5], 16)
	blue = int(color[5:], 16)

	lum = (.299 * red) + (.587 * green) + (.114 * blue)
	return lum / 255


def distance(left: Tuple[float, float], right: Tuple[float, float]) -> float:
	xl, yl = left
	xr, yr = right

	num = (xl - xr) ** 2 + (yl - yr) ** 2
	return math.sqrt(num)


def find_closest_point(point, points: List[Tuple[float, float]]) -> Tuple[float, float]:
	return min(points, key = lambda s: distance(s, point))


def relocate_point(point: Tuple[float, float], locations: List[Tuple[float, float]]) -> Tuple[float, float]:
	x_loc, y_loc = point
	for _ in range(10):
		closest_neighbor = find_closest_point((x_loc, y_loc), locations)
		y_is_close = math.isclose(y_loc, closest_neighbor[1], abs_tol = .1)
		y_is_almost_close = math.isclose(y_loc, closest_neighbor[1], abs_tol = .3)
		x_is_close = math.isclose(x_loc, closest_neighbor[0], abs_tol = 2)
		x_large = x_loc >= closest_neighbor[0]
		logger.debug(f"{x_loc}\t{y_loc}\t{closest_neighbor}\t{y_is_close}\t{y_is_almost_close}\t{x_is_close}\t{x_large}")
		if distance(closest_neighbor, (x_loc, y_loc)) > 1: break
		if y_is_close:
			if y_loc > closest_neighbor[1]:
				y_loc += random.uniform(.1, .2)
			else:
				y_loc -= random.uniform(.05, .10)
		elif y_is_almost_close and x_is_close and x_large:
			x_loc += .5
			break
		else:
			break
	return x_loc, y_loc


def annotate_axes(ax: Axes, points: Dict[str, Tuple[float, float]], annotations: Dict[str, List[str]], color_palette: Dict[str, str]) -> Axes:
	locations = list()
	for genotype_label, point in points.items():
		if genotype_label == 'genotype-0': continue
		label_properties = get_font_properties(color_palette[genotype_label])

		if locations:
			x_loc, y_loc = relocate_point(point, locations)
		else:
			x_loc, y_loc = point
		locations.append((x_loc, y_loc))
		genotype_annotations = annotations.get(genotype_label, [])
		try:
			genotype_annotations = genotype_annotations[:3]
		except IndexError:
			pass
		ax.text(
			x_loc, y_loc,
			"-" + "\n-".join(genotype_annotations),
			bbox = dict(facecolor = color_palette[genotype_label], alpha = 1),
			fontdict = label_properties
		)
	return ax


def generate_muller_plot(muller_df: pandas.DataFrame, trajectory_table: Optional[pandas.DataFrame], color_palette: Dict[str, str],
		output_filename: Path, annotations: Dict[str, List[str]] = None):
	"""
		Generates a muller diagram equivilent to r's ggmuller. The primary advantage is easier annotations.
	Parameters
	----------
	muller_df: pandas.DataFrame
	trajectory_table: pandas.DataFrame
	color_palette: Dict[str,str]
	output_filename: Path
	annotations: Dict[str, List[str]]
		A map of genotype labels to add to the plot.
	Returns
	-------
	ax: Axes
		The axes object containing the plot.
	"""
	points = get_coordinates(muller_df)

	# noinspection PyUnusedLocal,PyUnusedLocal
	fig, ax = plt.subplots(figsize = (12, 10))
	ax: Axes

	x, y, colors, labels = generate_muller_series(muller_df, color_palette)
	ax.stackplot(x, y, colors = colors, labels = labels)

	if annotations:
		annotate_axes(ax, points, annotations, color_palette)
	else:
		plt.legend(loc = 'right', bbox_to_anchor = (1.05, 0.5, 0.1, 0), title = 'Identity')
	ax.set_facecolor("#FFFFFF")
	ax.set_xlabel("Generation", fontsize = 20)
	ax.set_ylabel("Frequency", fontsize = 20)

	# Basic stacked area chart.
	ax.spines['right'].set_visible(False)
	ax.spines['top'].set_visible(False)
	ax.set_xlim(0, max(x))
	ax.set_ylim(0, 1)
	plt.tight_layout()
	plt.savefig(str(output_filename))
	plt.savefig(str(output_filename.with_suffix('.pdf')))
	plt.savefig(str(output_filename.with_suffix('.svg')))

	return ax


if __name__ == "__main__":
	pass
