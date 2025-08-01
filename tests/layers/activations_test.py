from deepctr.layers import activation

from keras.utils import CustomObjectScope
from tests.utils import layer_test


def test_dice():
    with CustomObjectScope({'Dice': activation.Dice}):
        layer_test(activation.Dice, kwargs={},
                   input_shape=(2, 3))
