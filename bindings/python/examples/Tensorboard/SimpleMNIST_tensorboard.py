# Copyright (c) Microsoft. All rights reserved.

# Licensed under the MIT license. See LICENSE.md file in the project root
# for full license information.
# ==============================================================================

import numpy as np
import sys
import os
from cntk import Trainer
from cntk.io import MinibatchSource, CTFDeserializer, StreamDef, StreamDefs, INFINITELY_REPEAT, FULL_DATA_SWEEP
from cntk.device import cpu, set_default_device
from cntk.learner import sgd
from cntk.ops import input_variable, cross_entropy_with_softmax, classification_error, relu, element_times, constant
import ipdb, pdb
import tensorflow as tf
from tensorflow.core.framework import summary_pb2
from cntk.utils import get_train_eval_criterion, get_train_loss, ProgressPrinter
from cntk.graph import *
abs_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(abs_path, "..", ".."))
from examples.common.nn import fully_connected_classifier_net, print_training_progress

def check_path(path):
    if not os.path.exists(path):
        readme_file = os.path.normpath(os.path.join(
            os.path.dirname(path), "..", "README.md"))
        raise RuntimeError(
            "File '%s' does not exist. Please follow the instructions at %s to download and prepare it." % (path, readme_file))

def create_reader(path, is_training, input_dim, label_dim):
    return MinibatchSource(CTFDeserializer(path, StreamDefs(
        features  = StreamDef(field='features', shape=input_dim, is_sparse=False),
        labels    = StreamDef(field='labels',   shape=label_dim, is_sparse=False)
    )), randomize=is_training, epoch_size = INFINITELY_REPEAT if is_training else FULL_DATA_SWEEP)


def summary_message(tag,value):
    return summary_pb2.Summary(value=[summary_pb2.Summary.Value
            (tag=tag,simple_value=value)])

# Creates and trains a feedforward classification model for MNIST images

def simple_mnist(debug_output=False):
    session = tf.Session()
    input_dim = 784
    num_output_classes = 10
    num_hidden_layers = 1
    hidden_layers_dim = 200

    # Input variables denoting the features and label data
    input = input_variable(input_dim, np.float32)
    label = input_variable(num_output_classes, np.float32)

    # Instantiate the feedforward classification model
    scaled_input = element_times(constant(0.00390625), input)
    netout = fully_connected_classifier_net(
        scaled_input, num_output_classes, hidden_layers_dim, num_hidden_layers, relu)

    
    create_tensorflow_graph(netout, session.graph)
    # x = tf.placeholder(netout.inputs[0].dtype, shape=netout.inputs[0].shape)
    # y = tf.placeholder(netout.inputs[1].dtype, shape=netout.inputs[1].shape)
    # with tf.name_scope(netout.root_function.name):
    # op = tf.add(x,y)
    # op2 = tf.add(op,y)

    ce = cross_entropy_with_softmax(netout, label)
    pe = classification_error(netout, label)

    try:
        rel_path = os.path.join(os.environ['CNTK_EXTERNAL_TESTDATA_SOURCE_DIRECTORY'],
                                *"Image/MNIST/v0/Train-28x28_cntk_text.txt".split("/"))
    except KeyError:
        rel_path = os.path.join(*"../../../../Examples/Image/DataSets/MNIST/Train-28x28_cntk_text.txt".split("/"))
    path = os.path.normpath(os.path.join(abs_path, rel_path))
    check_path(path)

    reader_train = create_reader(path, True, input_dim, num_output_classes)

    input_map = {
        input  : reader_train.streams.features,
        label  : reader_train.streams.labels
    }

    # Instantiate the trainer object to drive the model training
    trainer = Trainer(netout, ce, pe, sgd(netout.parameters, lr=0.003125))

    train_writer = tf.train.SummaryWriter(logdir='/home/alona/tflogs/graph', graph=session.graph, flush_secs=30)
    # test_writer = tf.train.SummaryWriter('/home/alona/tflogs/SimpleMNIST/test')

    # Get minibatches of images to train with and perform model training
    minibatch_size = 64
    num_samples_per_sweep = 6000
    num_sweeps_to_train_with = 2
    num_minibatches_to_train = (num_samples_per_sweep * num_sweeps_to_train_with) / minibatch_size
    training_progress_output_freq = 500



    if debug_output:
        training_progress_output_freq = training_progress_output_freq/4

    for i in range(0, int(num_minibatches_to_train)):
        mb = reader_train.next_minibatch(minibatch_size, input_map=input_map)
        x = trainer.train_minibatch(mb)
        # pdb.set_trace()
        # print_training_progress(trainer, i, training_progress_output_freq)
        train_writer.add_summary(summary_message("training_loss", trainer.previous_minibatch_loss_average), i)
        train_writer.add_summary(summary_message("train_eval_criterion", trainer.previous_minibatch_evaluation_average), i)


    # Load test data
    try:
        rel_path = os.path.join(os.environ['CNTK_EXTERNAL_TESTDATA_SOURCE_DIRECTORY'],
                                *"Image/MNIST/v0/Test-28x28_cntk_text.txt".split("/"))
    except KeyError:
        rel_path = os.path.join(*"../../../../Examples/Image/DataSets/MNIST/Test-28x28_cntk_text.txt".split("/"))
    path = os.path.normpath(os.path.join(abs_path, rel_path))
    check_path(path)

    reader_test = create_reader(path, False, input_dim, num_output_classes)

    input_map = {
        input  : reader_test.streams.features,
        label  : reader_test.streams.labels
    }

    # Test data for trained model
    test_minibatch_size = 1024
    num_samples = 10000
    num_minibatches_to_test = num_samples / test_minibatch_size
    test_result = 0.0
    for i in range(0, int(num_minibatches_to_test)):
        mb = reader_test.next_minibatch(test_minibatch_size, input_map=input_map)
        eval_error = trainer.test_minibatch(mb)
        train_writer.add_summary(summary_message("eval_error", eval_error), i)
        test_result = test_result + eval_error

    # print(output_function_graph(trainer.model))
    # output_function_graph(trainer.model, png_file_path="/home/alona/graph.png")
    # ipdb.set_trace()
    train_writer.close()


    # Average of evaluation errors of all test minibatches
    return test_result / num_minibatches_to_test


if __name__=='__main__':
    # Specify the target device to be used for computing, if you do not want to
    # use the best available one, e.g.
    # set_default_device(cpu())

    error = simple_mnist()
    print("Error: %f" % error)
