import collections
import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from loguru import logger


@dataclass
class Genotype:
	""" Used to consolidate known information for each genotype. Should probably be replaced by a dict later."""
	label: str
	color_clade: str
	color_custom: Optional[str]
	color_unique: str
	annotations: List[str]
	members: List[str]
	parent: Optional[str] = None


class GenotypeCollection(collections.UserDict):
	""" Provides methods for reproducing the old genotype-to-attribute maps"""

	def get_palette(self, which: str):
		return {k: (getattr(v, which) if v.color_custom is None else v.color_custom) for k, v in self.items()}

	def get(self, which: str) -> Dict[str, Union[str, List[str]]]:
		if 'color' in which:
			return self.get_palette(which)
		return {k: getattr(v, which) for k, v in self.items()}

	def trajectory_palette(self, which: str) -> Dict[str, str]:
		palette = dict()
		genotype_palette = self.get(which)
		for genotype_label, genotype_info in self.items():
			palette.update({m: genotype_palette[genotype_label] for m in genotype_info.members})
		return palette

	def get_annotation_map(self) -> Dict[str, List[Genotype]]:
		data = dict()
		for k, v in self.items():
			for annotation in v.annotations:
				if annotation not in data:
					data[annotation] = [k]
				else:
					data[annotation].append(k)

		return data

	def get_genotype_from_annotation(self, value: str) -> List[Genotype]:
		""" Try to find a given genotype based on the annotations that were extracted
			during the intitial data import."""
		annotation_map = self.get_annotation_map()
		if value in annotation_map:
			return annotation_map[value]
		else:
			# Print a list of similar annotations.
			logger.warning(f"Could not find a genotype matching annotation '{value}'")
			all_annotations = [i.annotations for i in self.values()]
			available = sorted(itertools.chain.from_iterable(all_annotations))
			try:
				from rapidfuzz import process
				similar = process.extract(value, available, score_cutoff=80)
				similar = [i[0] for i in similar]
			except ModuleNotFoundError:
				similar = [i for i in available if value in i]
			if similar:
				logger.warning(f"\tDid you mean one of these?")
				for i in similar:
					logger.warning(f"\t\t{i}")
			return []

	def get_trajectory_map(self) -> Dict[str, str]:
		t = dict()
		for label, value in self.items():
			t.update({m: label for m in value.members})
		return t
