import os
if os.environ['YOLO_SERVER'] == '1':
    import tensorflow as tf

import sys
cwd = os.getcwd()
os.chdir(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath('../tfrpc/client'))
from tf_wrapper import TFWrapper
os.chdir(cwd)

class BatchNormalization(tf.keras.layers.BatchNormalization):
    """
    Make trainable=False freeze BN for real (the og version is sad)
    """

    def call(self, x, training=False):
        if training is None:
            training = tf.constant(False)
        training = tf.logical_and(training, self.trainable)
        return super().call(x, training)
