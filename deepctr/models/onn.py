# -*- coding:utf-8 -*-
"""
Author:
    Weichen Shen, weichenswc@163.com

Reference:
    [1] Yang Y, Xu B, Shen F, et al. Operation-aware Neural Networks for User Response Prediction[J]. arXiv preprint arXiv:1904.12579, 2019. （https://arxiv.org/pdf/1904.12579）


"""

import itertools

from keras import backend as K
from keras.layers import (Dense, Embedding, Lambda,
                                            multiply, Flatten)
try:
    from keras.layers import BatchNormalization
except ImportError:
    import tensorflow as tf
    BatchNormalization = keras.layers.BatchNormalization
from keras.models import Model
from keras.regularizers import l2

from ..feature_column import SparseFeat, VarLenSparseFeat, build_input_features, get_linear_logit
from ..inputs import get_dense_input
from ..layers.core import DNN, PredictionLayer
from ..layers.sequence import SequencePoolingLayer
from ..layers.utils import concat_func, Hash, NoMask, add_func, combined_dnn_input


def ONN(linear_feature_columns, dnn_feature_columns, dnn_hidden_units=(256, 128, 64),
        l2_reg_embedding=1e-5, l2_reg_linear=1e-5, l2_reg_dnn=0, dnn_dropout=0,
        seed=1024, use_bn=True, reduce_sum=False, task='binary',
        ):
    """Instantiates the Operation-aware Neural Networks  architecture.

    :param linear_feature_columns: An iterable containing all the features used by linear part of the model.
    :param dnn_feature_columns: An iterable containing all the features used by deep part of the model.
    :param dnn_hidden_units: list,list of positive integer or empty list, the layer number and units in each layer of deep net
    :param l2_reg_embedding: float. L2 regularizer strength applied to embedding vector
    :param l2_reg_linear: float. L2 regularizer strength applied to linear part.
    :param l2_reg_dnn: float . L2 regularizer strength applied to DNN
    :param seed: integer ,to use as random seed.
    :param dnn_dropout: float in [0,1), the probability we will drop out a given DNN coordinate.
    :param use_bn: bool,whether use bn after ffm out or not
    :param reduce_sum: bool,whether apply reduce_sum on cross vector
    :param task: str, ``"binary"`` for  binary logloss or  ``"regression"`` for regression loss
    :return: A Keras model instance.
    """

    features = build_input_features(linear_feature_columns + dnn_feature_columns)

    inputs_list = list(features.values())

    linear_logit = get_linear_logit(features, linear_feature_columns, seed=seed, prefix='linear',
                                    l2_reg=l2_reg_linear)

    sparse_feature_columns = list(
        filter(lambda x: isinstance(x, SparseFeat), dnn_feature_columns)) if dnn_feature_columns else []
    varlen_sparse_feature_columns = list(
        filter(lambda x: isinstance(x, VarLenSparseFeat), dnn_feature_columns)) if dnn_feature_columns else []

    sparse_embedding = {fc_j.embedding_name: {fc_i.embedding_name: Embedding(fc_j.vocabulary_size, fc_j.embedding_dim,
                                                                             embeddings_initializer=fc_j.embeddings_initializer,
                                                                             embeddings_regularizer=l2(
                                                                                 l2_reg_embedding),
                                                                             mask_zero=isinstance(fc_j,
                                                                                                  VarLenSparseFeat),
                                                                             name='sparse_emb_' + str(
                                                                                 fc_j.embedding_name) + '_' + fc_i.embedding_name)
                                              for fc_i in
                                              sparse_feature_columns + varlen_sparse_feature_columns} for fc_j in
                        sparse_feature_columns + varlen_sparse_feature_columns}

    dense_value_list = get_dense_input(features, dnn_feature_columns)

    embed_list = []
    for fc_i, fc_j in itertools.combinations(sparse_feature_columns + varlen_sparse_feature_columns, 2):
        i_input = features[fc_i.name]
        if fc_i.use_hash:
            i_input = Hash(fc_i.vocabulary_size)(i_input)
        j_input = features[fc_j.name]
        if fc_j.use_hash:
            j_input = Hash(fc_j.vocabulary_size)(j_input)

        fc_i_embedding = feature_embedding(fc_i, fc_j, sparse_embedding, i_input)
        fc_j_embedding = feature_embedding(fc_j, fc_i, sparse_embedding, j_input)

        element_wise_prod = multiply([fc_i_embedding, fc_j_embedding])
        if reduce_sum:
            element_wise_prod = Lambda(lambda element_wise_prod: K.sum(
                element_wise_prod, axis=-1))(element_wise_prod)
        embed_list.append(element_wise_prod)

    ffm_out = Flatten()(concat_func(embed_list, axis=1))
    if use_bn:
        ffm_out = BatchNormalization()(ffm_out)
    dnn_input = combined_dnn_input([ffm_out], dense_value_list)
    dnn_out = DNN(dnn_hidden_units, l2_reg=l2_reg_dnn, dropout_rate=dnn_dropout)(dnn_input)
    dnn_logit = Dense(1, use_bias=False)(dnn_out)

    final_logit = add_func([dnn_logit, linear_logit])

    output = PredictionLayer(task)(final_logit)

    model = Model(inputs=inputs_list, outputs=output)
    return model


def feature_embedding(fc_i, fc_j, embedding_dict, input_feature):
    fc_i_embedding = embedding_dict[fc_i.name][fc_j.name](input_feature)
    if isinstance(fc_i, SparseFeat):
        return NoMask()(fc_i_embedding)
    else:
        return SequencePoolingLayer(fc_i.combiner, supports_masking=True)(fc_i_embedding)
