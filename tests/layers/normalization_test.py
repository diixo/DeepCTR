import pytest

from keras.utils import CustomObjectScope
from deepctr import layers
from tests.layers.interaction_test import BATCH_SIZE, FIELD_SIZE, EMBEDDING_SIZE
from tests.utils import layer_test


@pytest.mark.parametrize(
    'axis',
    [-1, -2
     ]
)
def test_LayerNormalization(axis):
    with CustomObjectScope({'LayerNormalization': layers.LayerNormalization}):
        layer_test(layers.LayerNormalization, kwargs={"axis": axis, }, input_shape=(
            BATCH_SIZE, FIELD_SIZE, EMBEDDING_SIZE))
