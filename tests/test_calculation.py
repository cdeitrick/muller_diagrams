import math

import pandas
import pytest

from muller.clustering.metrics import distance_calculator


@pytest.mark.parametrize("left,right,expected",
	[
		([0, 0, 0, 1, 1, 1, 1, 0], [0, 0, 0, 1, 1, 1, 1, 0], 0),
		([0, 0, 0, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 0, 0, 0], 0),
		([0, 0, 0, 1, 1, 1, 1, 0], [0, 0, 0, 1, 1, 1, 1, 1], 1),
		([0, 0, 0, 1, 1, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1], 1),
		([0, 0, 0, 1, 1, 0, 0, 0], [0, 0, 0, 0, 0, 1, 1, 1], 1),
		([0, 0, 0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 1, 1, 1], 1),
		([0, 0, 0, 1, 1, 1, 1], [0, 0, 0, 1, 1, 1, 1], 0)
	]
)
def test_fixed_overlap(left, right, expected):
	left = pandas.DataFrame(left)
	right = pandas.DataFrame(right)
	result = distance_calculator.fixed_overlap(left, right, 0.97)
	if math.isnan(result):
		result = 1
	assert expected == result
