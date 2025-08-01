# -*- coding:utf-8 -*-
"""
Author:
    Weichen Shen, weichenswc@163.com

    Shuxun Zan, zanshuxun@aliyun.com

Reference:
    [1] Wang R, Fu B, Fu G, et al. Deep & cross network for ad click predictions[C]//Proceedings of the ADKDD'17. ACM, 2017: 12. (https://arxiv.org/abs/1708.05123)

    [2] Wang R, Shivanna R, Cheng D Z, et al. DCN V2: Improved Deep & Cross Network and Practical Lessons for Web-scale Learning to Rank Systems[J]. 2020. (https://arxiv.org/abs/2008.13535)
"""
from keras.models import Model
from keras.layers import Dense, Concatenate

from ..feature_column import build_input_features, get_linear_logit, input_from_feature_columns
from ..layers.core import PredictionLayer, DNN
from ..layers.interaction import CrossNetMix
from ..layers.utils import add_func, combined_dnn_input


def DCNMix(linear_feature_columns, dnn_feature_columns, cross_num=2,
           dnn_hidden_units=(256, 128, 64), l2_reg_linear=1e-5, l2_reg_embedding=1e-5, low_rank=32, num_experts=4,
           l2_reg_cross=1e-5, l2_reg_dnn=0, seed=1024, dnn_dropout=0, dnn_use_bn=False,
           dnn_activation='relu', task='binary'):
    """Instantiates the Deep&Cross Network with mixture of experts architecture.

    :param linear_feature_columns: An iterable containing all the features used by linear part of the model.
    :param dnn_feature_columns: An iterable containing all the features used by deep part of the model.
    :param cross_num: positive integet,cross layer number
    :param dnn_hidden_units: list,list of positive integer or empty list, the layer number and units in each layer of DNN
    :param l2_reg_linear: float. L2 regularizer strength applied to linear part
    :param l2_reg_embedding: float. L2 regularizer strength applied to embedding vector
    :param l2_reg_cross: float. L2 regularizer strength applied to cross net
    :param l2_reg_dnn: float. L2 regularizer strength applied to DNN
    :param seed: integer ,to use as random seed.
    :param dnn_dropout: float in [0,1), the probability we will drop out a given DNN coordinate.
    :param dnn_use_bn: bool. Whether use BatchNormalization before activation or not DNN
    :param dnn_activation: Activation function to use in DNN
    :param low_rank: Positive integer, dimensionality of low-rank sapce.
    :param num_experts: Positive integer, number of experts.
    :param task: str, ``"binary"`` for  binary logloss or  ``"regression"`` for regression loss
    :return: A Keras model instance.

    """
    if len(dnn_hidden_units) == 0 and cross_num == 0:
        raise ValueError("Either hidden_layer or cross layer must > 0")

    features = build_input_features(dnn_feature_columns)
    inputs_list = list(features.values())

    linear_logit = get_linear_logit(features, linear_feature_columns, seed=seed, prefix='linear',
                                    l2_reg=l2_reg_linear)

    sparse_embedding_list, dense_value_list = input_from_feature_columns(features, dnn_feature_columns,
                                                                         l2_reg_embedding, seed)

    dnn_input = combined_dnn_input(sparse_embedding_list, dense_value_list)

    if len(dnn_hidden_units) > 0 and cross_num > 0:  # Deep & Cross
        deep_out = DNN(dnn_hidden_units, dnn_activation, l2_reg_dnn, dnn_dropout, dnn_use_bn, seed=seed)(dnn_input)
        cross_out = CrossNetMix(low_rank=low_rank, num_experts=num_experts, layer_num=cross_num,
                                l2_reg=l2_reg_cross)(dnn_input)
        stack_out = Concatenate()([cross_out, deep_out])
        final_logit = Dense(1, use_bias=False)(stack_out)
    elif len(dnn_hidden_units) > 0:  # Only Deep
        deep_out = DNN(dnn_hidden_units, dnn_activation, l2_reg_dnn, dnn_dropout, dnn_use_bn, seed=seed)(dnn_input)
        final_logit = Dense(1, use_bias=False,)(deep_out)
    elif cross_num > 0:  # Only Cross
        cross_out = CrossNetMix(low_rank=low_rank, num_experts=num_experts, layer_num=cross_num,
                                l2_reg=l2_reg_cross)(dnn_input)
        final_logit = Dense(1, use_bias=False, )(cross_out)
    else:  # Error
        raise NotImplementedError

    final_logit = add_func([final_logit, linear_logit])
    output = PredictionLayer(task)(final_logit)

    model = Model(inputs=inputs_list, outputs=output)

    return model
