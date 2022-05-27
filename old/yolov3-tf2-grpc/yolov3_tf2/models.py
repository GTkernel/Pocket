from absl import flags
from absl.flags import FLAGS
import numpy as np
# import tensorflow as tf
# from tensorflow.keras import Model
# from tensorflow.keras.layers import (
#     Add,
#     Concatenate,
#     Conv2D,
#     Input,
#     Lambda,
#     LeakyReLU,
#     MaxPool2D,
#     UpSampling2D,
#     ZeroPadding2D,
# )
# from tensorflow.keras.regularizers import l2
# from tensorflow.keras.losses import (
#     binary_crossentropy,
#     sparse_categorical_crossentropy
# )
# from .batch_norm import BatchNormalization ### need to be removed
from .utils import broadcast_iou

import sys, os, time
cwd = os.getcwd()
os.chdir(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath('../../tfrpc/client'))

# from tf_wrapper import TFWrapper, YoloWrapper POCKET_GRPC
from yolo_msgq import SharedMemoryChannel, PocketMessageChannel

os.chdir(cwd)
from yolo_pb2 import CallRequest

import random

flags.DEFINE_integer('yolo_max_boxes', 100,
                     'maximum number of boxes per image')
flags.DEFINE_float('yolo_iou_threshold', 0.5, 'iou threshold')
flags.DEFINE_float('yolo_score_threshold', 0.5, 'score threshold')

yolo_anchors = np.array([(10, 13), (16, 30), (33, 23), (30, 61), (62, 45),
                         (59, 119), (116, 90), (156, 198), (373, 326)],
                        np.float32) / 416
yolo_anchor_masks = np.array([[6, 7, 8], [3, 4, 5], [0, 1, 2]])

yolo_tiny_anchors = np.array([(10, 14), (23, 27), (37, 58),
                              (81, 82), (135, 169),  (344, 319)],
                             np.float32) / 416
yolo_tiny_anchor_masks = np.array([[3, 4, 5], [0, 1, 2]])



def debug(*args):
    class bcolors:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKCYAN = '\033[96m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'
    import inspect
    filename = inspect.stack()[1].filename
    lineno = inspect.stack()[1].lineno
    caller = inspect.stack()[1].function
    print(f'debug>> [{bcolors.WARNING}{filename}:{lineno}{bcolors.ENDC}, {caller}]', *args)



# def DarknetConv(x, filters, size, strides=1, batch_norm=True):
#     if strides == 1:
#         padding = 'same'
#     else:
#         x = ZeroPadding2D(((1, 0), (1, 0)))(x)  # top left half-padding
#         padding = 'valid'
#     x = Conv2D(filters=filters, kernel_size=size,
#                strides=strides, padding=padding,
#                use_bias=not batch_norm, kernel_regularizer=l2(0.0005))(x)
#     if batch_norm:
#         x = BatchNormalization()(x)
#         x = LeakyReLU(alpha=0.1)(x)
#     return x

def DarknetConv(stub, x: int, filters, size, strides=1, batch_norm=True):
    if strides == 1:
        padding = 'same'
    else:
        # x = ZeroPadding2D(((1, 0), (1, 0)))(x)  # top left half-padding
        zero_padding_2d_callable = TFWrapper.tf_keras_layers_ZeroPadding2D(stub, ((1, 0), (1, 0)))
        arg_x = CallRequest.ObjId()
        arg_x.obj_id = x
        arg_x.release = True
        x = TFWrapper.callable_emulator(stub, zero_padding_2d_callable, False, 1, '', arg_x)
        padding = 'valid'
    # x = Conv2D(filters=filters, kernel_size=size,
    #            strides=strides, padding=padding,
    #            use_bias=not batch_norm, kernel_regularizer=l2(0.0005))(x)

    arg_x = CallRequest.ObjId()
    arg_x.obj_id = x
    arg_x.release = True

    l2_val = TFWrapper.tf_keras_regularizers_l2(stub, 0.0005)
    conv2d_callable = TFWrapper.tf_keras_layers_Conv2D(stub, filters=filters, kernel_size=size, strides=strides, padding=padding, use_bias=not batch_norm, kernel_regularizer=l2_val)
    x = TFWrapper.callable_emulator(stub, conv2d_callable, False, 1, '', arg_x)
    if batch_norm:
        # x = BatchNormalization()(x)
        batch_norm_callable = YoloWrapper.BatchNormalization(stub)
        arg_x = CallRequest.ObjId()
        arg_x.obj_id = x
        arg_x.release = True
        x = TFWrapper.callable_emulator(stub, batch_norm_callable, False, 1, '', arg_x)
        # x = LeakyReLU(alpha=0.1)(x)
        leaky_relu_callable = TFWrapper.tf_keras_layers_LeakyReLU(stub, alpha=0.1)
        arg_x = CallRequest.ObjId()
        arg_x.obj_id = x
        arg_x.release = True
        x = TFWrapper.callable_emulator(stub, leaky_relu_callable, False, 1, '', arg_x)
    return x

def DarknetConv2(x, filters, size, strides=1, batch_norm=True):
    if strides == 1:
        padding = 'same'
    else:
        x = PocketMessageChannel.get_instance().tf_keras_layers_ZeroPadding2D(((1, 0), (1, 0)))(x)  # top left half-padding
        padding = 'valid'
    x = PocketMessageChannel.get_instance() \
                            .tf_keras_layers_Conv2D(filters=filters,
                                                    kernel_size=size,
                                                    strides=strides, 
                                                    padding=padding,
                                                    use_bias=not batch_norm, 
                                                    kernel_regularizer=PocketMessageChannel.get_instance().tf_keras_regularizers_l2(0.0005))(x)

    if batch_norm:
        x = PocketMessageChannel.get_instance().tf_keras_layers_BatchNormalization()(x)
        x = PocketMessageChannel.get_instance().tf_keras_layers_LeakyReLU(alpha=0.1)(x)
    return x

# def DarknetResidual(x, filters):
#     prev = x
#     x = DarknetConv(x, filters // 2, 1)
#     x = DarknetConv(x, filters, 3)
#     x = Add()([prev, x])
#     return x

def DarknetResidual(stub, x, filters):
    prev = x
    x = DarknetConv(stub, x, filters // 2, 1)
    x = DarknetConv(stub, x, filters, 3)
    # x = Add()([prev, x])
    add_callable = TFWrapper.tf_keras_layers_Add(stub)
    arg_x = CallRequest.ObjId()
    arg_x.obj_id = x
    arg_x.release = True
    arg_prev = CallRequest.ObjId()
    arg_prev.obj_id = prev
    arg_prev.release = True
    x = TFWrapper.callable_emulator(stub, add_callable, False, 1, '', arg_prev, arg_x)
    return x

def DarknetResidual2(x, filters):
    prev = x
    x = DarknetConv2(x, filters // 2, 1)
    x = DarknetConv2(x, filters, 3)
    x = PocketMessageChannel.get_instance().tf_keras_layers_Add()([prev, x])
    return x


# def DarknetBlock(x, filters, blocks):
#     x = DarknetConv(x, filters, 3, strides=2)
#     for _ in range(blocks):
#         x = DarknetResidual(x, filters)
#     return x

def DarknetBlock(stub, x, filters, blocks):
    x = DarknetConv(stub, x, filters, 3, strides=2)
    for _ in range(blocks):
        x = DarknetResidual(stub, x, filters)
    return x

def DarknetBlock2(x, filters, blocks):
    x = DarknetConv2(x, filters, 3, strides=2)
    for _ in range(blocks):
        x = DarknetResidual2(x, filters)
    return x

# def Darknet(name=None):
#     x = inputs = Input([None, None, 3])
#     x = DarknetConv(x, 32, 3)
#     x = DarknetBlock(x, 64, 1)
#     x = DarknetBlock(x, 128, 2)  # skip connection
#     x = x_36 = DarknetBlock(x, 256, 8)  # skip connection
#     x = x_61 = DarknetBlock(x, 512, 8)
#     x = DarknetBlock(x, 1024, 4)
#     return tf.keras.Model(inputs, (x_36, x_61, x), name=name)


def Darknet(stub=None, name=None):
    x = inputs = TFWrapper.tf_keras_layers_Input(stub, shape=[None, None, 3])
    x = DarknetConv(stub, x, 32, 3)
    x = DarknetBlock(stub, x, 64, 1)
    x = DarknetBlock(stub, x, 128, 2)  # skip connection
    x = x_36 = DarknetBlock(stub, x, 256, 8)  # skip connection
    x = x_61 = DarknetBlock(stub, x, 512, 8)
    x = DarknetBlock(stub, x, 1024, 4)

    # return tf.keras.Model(inputs, (x_36, x_61, x), name=name)
    keras_model_id = TFWrapper.tf_keras_Model(stub, [inputs], (x_36, x_61, x), name=name)
    return keras_model_id

def Darknet2(name=None):
    x = inputs = PocketMessageChannel.get_instance().tf_keras_layers_Input([None, None, 3])
    x = DarknetConv2(x, 32, 3)
    x = DarknetBlock2(x, 64, 1)
    x = DarknetBlock2(x, 128, 2)  # skip connection
    x = x_36 = DarknetBlock2(x, 256, 8)  # skip connection
    x = x_61 = DarknetBlock2(x, 512, 8)
    x = DarknetBlock2(x, 1024, 4)
    return PocketMessageChannel.get_instance().tf_keras_Model(inputs, (x_36, x_61, x), name=name)

def DarknetTiny(stub, name=None):
    x = inputs = Input([None, None, 3])
    x = DarknetConv(stub, x, 16, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(stub, x, 32, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(stub, x, 64, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(stub, x, 128, 3)
    x = MaxPool2D(2, 2, 'same')(x)
    x = x_8 = DarknetConv(stub, x, 256, 3)  # skip connection
    x = MaxPool2D(2, 2, 'same')(x)
    x = DarknetConv(stub, x, 512, 3)
    x = MaxPool2D(2, 1, 'same')(x)
    x = DarknetConv(stub, x, 1024, 3)
    return tf.keras.Model(inputs, (x_8, x), name=name)

# def DarknetTiny(name=None):
#     x = inputs = Input([None, None, 3])
#     x = DarknetConv(x, 16, 3)
#     x = MaxPool2D(2, 2, 'same')(x)
#     x = DarknetConv(x, 32, 3)
#     x = MaxPool2D(2, 2, 'same')(x)
#     x = DarknetConv(x, 64, 3)
#     x = MaxPool2D(2, 2, 'same')(x)
#     x = DarknetConv(x, 128, 3)
#     x = MaxPool2D(2, 2, 'same')(x)
#     x = x_8 = DarknetConv(x, 256, 3)  # skip connection
#     x = MaxPool2D(2, 2, 'same')(x)
#     x = DarknetConv(x, 512, 3)
#     x = MaxPool2D(2, 1, 'same')(x)
#     x = DarknetConv(x, 1024, 3)
#     return tf.keras.Model(inputs, (x_8, x), name=name)


def YoloConv(stub, filters, name=None):
    def yolo_conv(x_in):
        if isinstance(x_in, tuple):
            # inputs = Input(x_in[0].shape[1:]), Input(x_in[1].shape[1:])
            # x, x_skip = inputs
            shape_of_input_0 = TFWrapper.attribute_tensor_shape(stub, [x_in[0]], start=1, end=0)
            shape_of_input_1 = TFWrapper.attribute_tensor_shape(stub, [x_in[1]], start=1, end=0)
            x = TFWrapper.tf_keras_layers_Input(stub, shape_of_input_0[1:])
            x_skip = TFWrapper.tf_keras_layers_Input(stub, shape_of_input_1[1:])
            inputs = x, x_skip

            # concat with skip connection
            x = DarknetConv(stub, x, filters, 1)
            # x = UpSampling2D(2)(x)
            upsampling_callable_id = TFWrapper.tf_keras_layers_UpSampling2D(stub, 2)
            arg_x = CallRequest.ObjId()
            arg_x.obj_id = x
            arg_x.release = True
            x = TFWrapper.callable_emulator(stub, upsampling_callable_id, False, 1, '', arg_x)
            
            # x = Concatenate()([x, x_skip])
            concatenate_callable_id = TFWrapper.tf_keras_layers_Concatenate(stub)
            arg_x.obj_id = x
            arg_x_skip = CallRequest.ObjId()
            arg_x_skip.obj_id = x_skip
            arg_x_skip.release = True
            x = TFWrapper.callable_emulator(stub, concatenate_callable_id, False, 1, '', arg_x, arg_x_skip)
        else:
            # x = inputs = Input(x_in.shape[1:])
            shape_of_input = TFWrapper.attribute_tensor_shape(stub, x_in, start=1, end=0)
            x = inputs = TFWrapper.tf_keras_layers_Input(stub, shape_of_input[1:])

        x = DarknetConv(stub, x, filters, 1)
        x = DarknetConv(stub, x, filters * 2, 3)
        x = DarknetConv(stub, x, filters, 1)
        x = DarknetConv(stub, x, filters * 2, 3)
        x = DarknetConv(stub, x, filters, 1)

        # return tf.keras.Model(inputs, x, name=name)(x_in)
        if isinstance(inputs, tuple):
            keras_model_id = TFWrapper.tf_keras_Model(stub, inputs, [x], name=name)
        else:
            keras_model_id = TFWrapper.tf_keras_Model(stub, [inputs], [x], name=name)

        arg_x_in = []
        for elem in x_in:
            arg = CallRequest.ObjId()
            arg.obj_id = elem
            arg.release = True
            arg_x_in.append(arg)

        output = TFWrapper.callable_emulator(stub, keras_model_id, False, 1, '', *arg_x_in)
        return output
    return yolo_conv

# def YoloConv(filters, name=None):
#     def yolo_conv(x_in):
#         if isinstance(x_in, tuple):
#             inputs = Input(x_in[0].shape[1:]), Input(x_in[1].shape[1:])
#             x, x_skip = inputs

#             # concat with skip connection
#             x = DarknetConv(x, filters, 1)
#             x = UpSampling2D(2)(x)
#             x = Concatenate()([x, x_skip])
#         else:
#             x = inputs = Input(x_in.shape[1:])

#         x = DarknetConv(x, filters, 1)
#         x = DarknetConv(x, filters * 2, 3)
#         x = DarknetConv(x, filters, 1)
#         x = DarknetConv(x, filters * 2, 3)
#         x = DarknetConv(x, filters, 1)
#         return tf.keras.Model(inputs, x, name=name)(x_in)
#     return yolo_conv

def YoloConv2(filters, name=None):
    def yolo_conv(x_in):
        if isinstance(x_in, tuple):
            inputs = PocketMessageChannel.get_instance().tf_keras_layers_Input(x_in[0].shape[1:]), PocketMessageChannel.get_instance().tf_keras_layers_Input(x_in[1].shape[1:])
            x, x_skip = inputs

            # concat with skip connection
            x = DarknetConv2(x, filters, 1)
            x = PocketMessageChannel.get_instance().tf_keras_layers_UpSampling2D(2)(x)
            x = PocketMessageChannel.get_instance().tf_keras_layers_Concatenate()([x, x_skip])
        else:
            x = inputs = PocketMessageChannel.get_instance().tf_keras_layers_Input(x_in.shape[1:])

        x = DarknetConv2(x, filters, 1)
        x = DarknetConv2(x, filters * 2, 3)
        x = DarknetConv2(x, filters, 1)
        x = DarknetConv2(x, filters * 2, 3)
        x = DarknetConv2(x, filters, 1)
        return PocketMessageChannel.get_instance().tf_keras_Model(inputs, x, name=name)(x_in)
    return yolo_conv


# def YoloConvTiny(filters, name=None):
#     def yolo_conv(x_in):
#         if isinstance(x_in, tuple):
#             inputs = Input(x_in[0].shape[1:]), Input(x_in[1].shape[1:])
#             x, x_skip = inputs

#             # concat with skip connection
#             x = DarknetConv(x, filters, 1)
#             x = UpSampling2D(2)(x)
#             x = Concatenate()([x, x_skip])
#         else:
#             x = inputs = Input(x_in.shape[1:])
#             x = DarknetConv(x, filters, 1)

#         return tf.keras.Model(inputs, x, name=name)(x_in)
#     return yolo_conv

def YoloConvTiny(stub, filters, name=None):
    def yolo_conv(x_in):
        if isinstance(x_in, tuple):
            inputs = Input(x_in[0].shape[1:]), Input(x_in[1].shape[1:])
            x, x_skip = inputs

            # concat with skip connection
            x = DarknetConv(stub, x, filters, 1)
            x = UpSampling2D(2)(x)
            x = Concatenate()([x, x_skip])
        else:
            x = inputs = Input(x_in.shape[1:])
            x = DarknetConv(stub, x, filters, 1)

        return tf.keras.Model(inputs, x, name=name)(x_in)
    return yolo_conv


def YoloOutput(stub, filters, anchors, classes, name=None):
    def yolo_output(x_in):
        # x = inputs = Input(x_in.shape[1:])
        shape_of_input = TFWrapper.attribute_tensor_shape(stub, x_in, start=1, end=0)
        x = inputs = TFWrapper.tf_keras_layers_Input(stub, shape_of_input[1:], name='input')

        x = DarknetConv(stub, x, filters * 2, 3)
        x = DarknetConv(stub, x, anchors * (classes + 5), 1, batch_norm=False)
        # x = Lambda(lambda x: tf.reshape(x, (-1, tf.shape(x)[1], tf.shape(x)[2],
                                            # anchors, classes + 5)))(x)
        lambda_x_str = f'tf.reshape(x, (-1, tf.shape(x)[1], tf.shape(x)[2], {anchors}, {classes} + 5))'
        # lambda_x_str = f'tf.keras.layers.Reshape((-1, tf.shape(x)[1], tf.shape(x)[2], {anchors}, {classes} + 5))(x)'
        # lambda_x_str = f'lambda x: tf.keras.layers.Reshape((-1, tf.shape(x)[1], tf.shape(x)[2], {anchors}, {classes} + 5))(x)'
        callable_layer_object = TFWrapper.tf_keras_layers_Lambda(stub, lambda_x_str)
        # callable_layer_object = Lambda(lambda_obj_id) ### Todo

        arg_x = CallRequest.ObjId()
        arg_x.obj_id = x
        arg_x.release = True
        x = TFWrapper.callable_emulator(stub, callable_layer_object, False, 1, '', arg_x)

        # return tf.keras.Model(inputs, x, name=name)(x_in)
        keras_model_id = TFWrapper.tf_keras_Model(stub, [inputs], [x], name=name)
        
        arg_x_in = []
        for elem in x_in:
            arg = CallRequest.ObjId()
            arg.obj_id = elem
            arg.release = True
            arg_x_in.append(arg)
        output = TFWrapper.callable_emulator(stub, keras_model_id, False, 1, '', *arg_x_in)
        return output
    return yolo_output

# def YoloOutput(filters, anchors, classes, name=None):
#     def yolo_output(x_in):
#         x = inputs = Input(x_in.shape[1:])
#         x = DarknetConv(x, filters * 2, 3)
#         x = DarknetConv(x, anchors * (classes + 5), 1, batch_norm=False)
#         x = Lambda(lambda x: tf.reshape(x, (-1, tf.shape(x)[1], tf.shape(x)[2],
#                                             anchors, classes + 5)))(x)
#         return tf.keras.Model(inputs, x, name=name)(x_in)
#     return yolo_output


def YoloOutput2(filters, anchors, classes, name=None):
    def yolo_output(x_in):
        x = inputs = PocketMessageChannel.get_instance().tf_keras_layers_Input(x_in.shape[1:])
        x = DarknetConv2(x, filters * 2, 3)
        x = DarknetConv2(x, anchors * (classes + 5), 1, batch_norm=False)
        x = PocketMessageChannel.get_instance().tf_keras_layers_Lambda(lambda x: tf.reshape(x, (-1, tf.shape(x)[1], tf.shape(x)[2], anchors, classes + 5)), context=locals())(x)
        return PocketMessageChannel.get_instance().tf_keras_Model(inputs, x, name=name)(x_in)
    return yolo_output

### moved_to_server side
# def yolo_boxes(pred, anchors, classes):
#     # pred: (batch_size, grid, grid, anchors, (x, y, w, h, obj, ...classes))
#     grid_size = tf.shape(pred)[1]
#     box_xy, box_wh, objectness, class_probs = tf.split(
#         pred, (2, 2, 1, classes), axis=-1)

#     box_xy = tf.sigmoid(box_xy)
#     objectness = tf.sigmoid(objectness)
#     class_probs = tf.sigmoid(class_probs)
#     pred_box = tf.concat((box_xy, box_wh), axis=-1)  # original xywh for loss

#     # !!! grid[x][y] == (y, x)
#     grid = tf.meshgrid(tf.range(grid_size), tf.range(grid_size))
#     grid = tf.expand_dims(tf.stack(grid, axis=-1), axis=2)  # [gx, gy, 1, 2]

#     box_xy = (box_xy + tf.cast(grid, tf.float32)) / \
#         tf.cast(grid_size, tf.float32)
#     box_wh = tf.exp(box_wh) * anchors

#     box_x1y1 = box_xy - box_wh / 2
#     box_x2y2 = box_xy + box_wh / 2
#     bbox = tf.concat([box_x1y1, box_x2y2], axis=-1)

#     return bbox, objectness, class_probs, pred_box

### moved to server
# def yolo_nms(outputs, anchors, masks, classes):
#     # boxes, conf, type
#     b, c, t = [], [], []

#     for o in outputs:
#         b.append(tf.reshape(o[0], (tf.shape(o[0])[0], -1, tf.shape(o[0])[-1])))
#         c.append(tf.reshape(o[1], (tf.shape(o[1])[0], -1, tf.shape(o[1])[-1])))
#         t.append(tf.reshape(o[2], (tf.shape(o[2])[0], -1, tf.shape(o[2])[-1])))

#     bbox = tf.concat(b, axis=1)
#     confidence = tf.concat(c, axis=1)
#     class_probs = tf.concat(t, axis=1)

#     scores = confidence * class_probs
#     boxes, scores, classes, valid_detections = tf.image.combined_non_max_suppression(
#         boxes=tf.reshape(bbox, (tf.shape(bbox)[0], -1, 1, 4)),
#         scores=tf.reshape(
#             scores, (tf.shape(scores)[0], -1, tf.shape(scores)[-1])),
#         max_output_size_per_class=FLAGS.yolo_max_boxes,
#         max_total_size=FLAGS.yolo_max_boxes,
#         iou_threshold=FLAGS.yolo_iou_threshold,
#         score_threshold=FLAGS.yolo_score_threshold
#     )

#     return boxes, scores, classes, valid_detections

# def YoloV3(size=None, channels=3, anchors=yolo_anchors,
#            masks=yolo_anchor_masks, classes=80, training=False):
#     x = inputs = Input([size, size, channels], name='input')

#     x_36, x_61, x = Darknet(name='yolo_darknet')(x)

#     x = YoloConv(512, name='yolo_conv_0')(x)
#     output_0 = YoloOutput(512, len(masks[0]), classes, name='yolo_output_0')(x)

#     x = YoloConv(256, name='yolo_conv_1')((x, x_61))
#     output_1 = YoloOutput(256, len(masks[1]), classes, name='yolo_output_1')(x)

#     x = YoloConv(128, name='yolo_conv_2')((x, x_36))
#     output_2 = YoloOutput(128, len(masks[2]), classes, name='yolo_output_2')(x)

#     if training:
#         return tf.keras.Model(inputs, (output_0, output_1, output_2), name='yolov3')

#     boxes_0 = Lambda(lambda x: yolo_boxes(x, anchors[masks[0]], classes),
#                      name='yolo_boxes_0')(output_0)
#     boxes_1 = Lambda(lambda x: yolo_boxes(x, anchors[masks[1]], classes),
#                      name='yolo_boxes_1')(output_1)
#     boxes_2 = Lambda(lambda x: yolo_boxes(x, anchors[masks[2]], classes),
#                      name='yolo_boxes_2')(output_2)

#     outputs = Lambda(lambda x: yolo_nms(x, anchors, masks, classes),
#                      name='yolo_nms')((boxes_0[:3], boxes_1[:3], boxes_2[:3]))

#     return tf.keras.Model(inputs, outputs, name='yolov3')

def YoloV32(size=None, channels=3, classes=80, training=False):
# anchors=yolo_anchors,
        #    masks=yolo_anchor_masks, 
    import logging
    try:
        # Invalid # keras_model = tf.Graph.get_tensor_by_name('yolov3')
        is_exist, keras_model = PocketMessageChannel.get_instance().check_if_model_exist('yolov3')
    except KeyError as e:
        is_exist = False

    if is_exist:
        if keras_model == None:
            while True:
                time.sleep(random.uniform(1,3))
                is_exist, keras_model = PocketMessageChannel.get_instance().check_if_model_exist('yolov3')
                if keras_model != None:
                    break
        else:
            return keras_model
    
    # x = inputs = Input([size, size, channels], name='input')
    x = inputs = PocketMessageChannel.get_instance().tf_keras_layers_Input([size, size, channels], name='input')

    # x_36, x_61, x = Darknet(name='yolo_darknet')(x)
    x_36, x_61, x = Darknet2(name='yolo_darknet')(x)

    x = YoloConv2(512, name='yolo_conv_0')(x)
    output_0 = YoloOutput2(512, len(yolo_anchor_masks[0]), classes, name='yolo_output_0')(x)

    x = YoloConv2(256, name='yolo_conv_1')((x, x_61))
    output_1 = YoloOutput2(256, len(yolo_anchor_masks[1]), classes, name='yolo_output_1')(x)

    x = YoloConv2(128, name='yolo_conv_2')((x, x_36))
    output_2 = YoloOutput2(128, len(yolo_anchor_masks[2]), classes, name='yolo_output_2')(x)


    boxes_0 = PocketMessageChannel.get_instance().tf_keras_layers_Lambda(lambda x: yolo_boxes(x, yolo_anchors[yolo_anchor_masks[0]], classes),
                    name='yolo_boxes_0', context=locals())(output_0)


    boxes_1 = PocketMessageChannel.get_instance().tf_keras_layers_Lambda(lambda x: yolo_boxes(x, yolo_anchors[yolo_anchor_masks[1]], classes),
                     name='yolo_boxes_1', context=locals())(output_1)

    boxes_2 = PocketMessageChannel.get_instance().tf_keras_layers_Lambda(lambda x: yolo_boxes(x, yolo_anchors[yolo_anchor_masks[2]], classes),
                     name='yolo_boxes_2', context=locals())(output_2)


    outputs = PocketMessageChannel.get_instance().tf_keras_layers_Lambda(lambda x: yolo_nms(x, yolo_anchors, yolo_anchor_masks, classes),
                     name='yolo_nms', context=locals())((boxes_0[:3], boxes_1[:3], boxes_2[:3]))

    return PocketMessageChannel.get_instance().tf_keras_Model(inputs, outputs, name='yolov3')

def YoloV3(stub=None, size=None, channels=3, anchors=yolo_anchors,
           masks=yolo_anchor_masks, classes=80, training=False):

    try:
        # Invalid # keras_model = tf.Graph.get_tensor_by_name('yolov3')
        if FLAGS.comm == 'grpc':
            is_exist, keras_model_id = YoloWrapper.CheckIfModelExist(stub, name='yolov3', plan_to_make=True)
        elif FLAGS.comm == 'msgq':
            is_exist, keras_model = PocketMessageChannel.get_instance().check_if_model_exist('yolov3')
    except KeyError as e:
        is_exist = False
    else:
        is_exist = True

    if FLAGS.comm == 'grpc':
        if is_exist:
            if keras_model_id is 0:
                while True:
                    time.sleep(random.uniform(1, 3))
                    _, keras_model_id = YoloWrapper.CheckIfModelExist(stub, name='yolov3', plan_to_make=True)
                    if keras_model_id is not 0:
                        return keras_model_id
            else:
                return keras_model_id
    elif FLAGS.comm == 'msgq':
        if is_exist:
            if keras_model == None:
                while True:
                    time.sleep(random.uniform(1,3))
                    keras_model = PocketMessageChannel.get_instance().check_if_model_exist('yolov3')
                    if keras_model != None:
                        break
            else:
                return keras_model
    
    # x = inputs = Input([size, size, channels], name='input')
    if FLAGS.comm == 'grpc':
        x = inputs = TFWrapper.tf_keras_layers_Input(stub, [size, size, channels], name='input')
    if FLAGS.comm == 'msgq':
        x = inputs = PocketMessageChannel.get_instance().tf_keras_layers_Input([size, size, channels], name='input')

    # x_36, x_61, x = Darknet(name='yolo_darknet')(x)
    if FLAGS.comm == 'grpc':
        callable_model_obj_id = Darknet(stub, name='yolo_darknet')
        arg_x = CallRequest.ObjId()
        arg_x.obj_id = x
        arg_x.release = True
        x_36, x_61, x = TFWrapper.callable_emulator(stub, callable_model_obj_id, False, 3, '', arg_x)
    if FLAGS.comm == 'msgq':
        x_36, x_61, x = Darknet2(name='yolo_darknet')(x)
    
    if FLAGS.comm == 'grpc':
        x = YoloConv(stub, 512, name='yolo_conv_0')([x])
        output_0 = YoloOutput(stub, 512, len(masks[0]), classes, name='yolo_output_0')([x])

        x = YoloConv(stub, 256, name='yolo_conv_1')((x, x_61))
        output_1 = YoloOutput(stub, 256, len(masks[1]), classes, name='yolo_output_1')([x])

        x = YoloConv(stub, 128, name='yolo_conv_2')((x, x_36))
        output_2 = YoloOutput(stub, 128, len(masks[2]), classes, name='yolo_output_2')([x])

        if training:
            return tf.keras.Model(inputs, (output_0, output_1, output_2), name='yolov3')
    elif FLAGS.comm == 'msgq':
        x = YoloConv2(512, name='yolo_conv_0')(x)
        output_0 = YoloOutput2(512, len(masks[0]), classes, name='yolo_output_0')(x)

        x = YoloConv2(256, name='yolo_conv_1')((x, x_61))
        output_1 = YoloOutput2(256, len(masks[1]), classes, name='yolo_output_1')(x)

        x = YoloConv2(128, name='yolo_conv_2')((x, x_36))
        output_2 = YoloOutput2(128, len(masks[2]), classes, name='yolo_output_2')(x)

    debug('Happily DONE!!!!')
    exit()

    # boxes_0 = Lambda(lambda x: yolo_boxes(x, anchors[masks[0]], classes),
    #                  name='yolo_boxes_0')(output_0)
    lambda_str = f'yolo_boxes(x, yolo_anchors[yolo_anchor_masks[0]], 80)'
    lambda_callable_id = TFWrapper.tf_keras_layers_Lambda(stub, lambda_str, name='yolo_boxes_0')
    arg_boxes_0 = CallRequest.ObjId()
    arg_boxes_0.obj_id = output_0
    arg_boxes_0.release = True
    boxes_0 = TFWrapper.callable_emulator(stub, lambda_callable_id, False, 1, '', arg_boxes_0)
    boxes_0_0_to_3 = TFWrapper.get_iterable_slicing(stub, boxes_0, 0, 3)

    # boxes_1 = Lambda(lambda x: yolo_boxes(x, anchors[masks[1]], classes),
                    #  name='yolo_boxes_1')(output_1)
    lambda_str = f'yolo_boxes(x, yolo_anchors[yolo_anchor_masks[1]], 80)'
    lambda_callable_id = TFWrapper.tf_keras_layers_Lambda(stub, lambda_str, name='yolo_boxes_1')
    arg_boxes_1 = CallRequest.ObjId()
    arg_boxes_1.obj_id = output_1
    arg_boxes_1.release = True
    boxes_1 = TFWrapper.callable_emulator(stub, lambda_callable_id, False, 1, '', arg_boxes_1)
    boxes_1_0_to_3 = TFWrapper.get_iterable_slicing(stub, boxes_1, 0, 3)

    # boxes_2 = Lambda(lambda x: yolo_boxes(x, anchors[masks[2]], classes),
    #                  name='yolo_boxes_2')(output_2)
    lambda_str = f'yolo_boxes(x, yolo_anchors[yolo_anchor_masks[2]], 80)'
    lambda_callable_id = TFWrapper.tf_keras_layers_Lambda(stub, lambda_str, name='yolo_boxes_2')
    arg_boxes_2 = CallRequest.ObjId()
    arg_boxes_2.obj_id = output_2
    arg_boxes_2.release = True
    boxes_2 = TFWrapper.callable_emulator(stub, lambda_callable_id, False, 1, '', arg_boxes_2)
    boxes_2_0_to_3 = TFWrapper.get_iterable_slicing(stub, boxes_2, 0, 3)

    # outputs = Lambda(lambda x: yolo_nms(x, anchors, masks, classes),
    #                  name='yolo_nms')((boxes_0[:3], boxes_1[:3], boxes_2[:3]))
    lambda_str = f'yolo_nms(x, yolo_anchors, yolo_anchor_masks, 80)'
    lambda_callable_id = TFWrapper.tf_keras_layers_Lambda(stub, lambda_str, name='yolo_nms')
    
    arg_boxes_0_0_to_3 = CallRequest.ObjId()
    arg_boxes_0_0_to_3.obj_id = boxes_0_0_to_3
    arg_boxes_0_0_to_3.release = True

    arg_boxes_1_0_to_3 = CallRequest.ObjId()
    arg_boxes_1_0_to_3.obj_id = boxes_1_0_to_3
    arg_boxes_1_0_to_3.release = True

    arg_boxes_2_0_to_3 = CallRequest.ObjId()
    arg_boxes_2_0_to_3.obj_id = boxes_2_0_to_3
    arg_boxes_2_0_to_3.release = True

    arg_outputs = (arg_boxes_0_0_to_3, arg_boxes_1_0_to_3, arg_boxes_2_0_to_3)
    outputs = TFWrapper.callable_emulator(stub, lambda_callable_id, False, 1, '', *arg_outputs)

    # return tf.keras.Model(inputs, outputs, name='yolov3')
    keras_model_id = TFWrapper.tf_keras_Model(stub, [inputs], [outputs], name='yolov3', fixed=True)
    return keras_model_id
    

# def YoloV3Tiny(size=None, channels=3, anchors=yolo_tiny_anchors,
#                masks=yolo_tiny_anchor_masks, classes=80, training=False):
#     x = inputs = Input([size, size, channels], name='input')

#     x_8, x = DarknetTiny(name='yolo_darknet')(x)

#     x = YoloConvTiny(256, name='yolo_conv_0')(x)
#     output_0 = YoloOutput(256, len(masks[0]), classes, name='yolo_output_0')(x)

#     x = YoloConvTiny(128, name='yolo_conv_1')((x, x_8))
#     output_1 = YoloOutput(128, len(masks[1]), classes, name='yolo_output_1')(x)

#     if training:
#         return tf.keras.Model(inputs, (output_0, output_1), name='yolov3')

#     boxes_0 = Lambda(lambda x: yolo_boxes(x, anchors[masks[0]], classes),
#                      name='yolo_boxes_0')(output_0)
#     boxes_1 = Lambda(lambda x: yolo_boxes(x, anchors[masks[1]], classes),
#                      name='yolo_boxes_1')(output_1)
#     outputs = Lambda(lambda x: yolo_nms(x, anchors, masks, classes),
#                      name='yolo_nms')((boxes_0[:3], boxes_1[:3]))
#     return tf.keras.Model(inputs, outputs, name='yolov3_tiny')

def YoloV3Tiny(stub, size=None, channels=3, anchors=yolo_tiny_anchors,
               masks=yolo_tiny_anchor_masks, classes=80, training=False):
    x = inputs = Input([size, size, channels], name='input')

    x_8, x = DarknetTiny(stub, name='yolo_darknet')(x)

    x = YoloConvTiny(stub, 256, name='yolo_conv_0')(x)
    output_0 = YoloOutput(stub, 256, len(masks[0]), classes, name='yolo_output_0')(x)

    x = YoloConvTiny(stub, 128, name='yolo_conv_1')((x, x_8))
    output_1 = YoloOutput(stub, 128, len(masks[1]), classes, name='yolo_output_1')(x)

    if training:
        return tf.keras.Model(inputs, (output_0, output_1), name='yolov3')

    boxes_0 = Lambda(lambda x: yolo_boxes(x, anchors[masks[0]], classes),
                     name='yolo_boxes_0')(output_0)
    boxes_1 = Lambda(lambda x: yolo_boxes(x, anchors[masks[1]], classes),
                     name='yolo_boxes_1')(output_1)
    outputs = Lambda(lambda x: yolo_nms(x, anchors, masks, classes),
                     name='yolo_nms')((boxes_0[:3], boxes_1[:3]))
    return tf.keras.Model(inputs, outputs, name='yolov3_tiny')


def YoloLoss(anchors, classes=80, ignore_thresh=0.5):
    def yolo_loss(y_true, y_pred):
        # 1. transform all pred outputs
        # y_pred: (batch_size, grid, grid, anchors, (x, y, w, h, obj, ...cls))
        pred_box, pred_obj, pred_class, pred_xywh = yolo_boxes(
            y_pred, anchors, classes)
        pred_xy = pred_xywh[..., 0:2]
        pred_wh = pred_xywh[..., 2:4]

        # 2. transform all true outputs
        # y_true: (batch_size, grid, grid, anchors, (x1, y1, x2, y2, obj, cls))
        true_box, true_obj, true_class_idx = tf.split(
            y_true, (4, 1, 1), axis=-1)
        true_xy = (true_box[..., 0:2] + true_box[..., 2:4]) / 2
        true_wh = true_box[..., 2:4] - true_box[..., 0:2]

        # give higher weights to small boxes
        box_loss_scale = 2 - true_wh[..., 0] * true_wh[..., 1]

        # 3. inverting the pred box equations
        grid_size = tf.shape(y_true)[1]
        grid = tf.meshgrid(tf.range(grid_size), tf.range(grid_size))
        grid = tf.expand_dims(tf.stack(grid, axis=-1), axis=2)
        true_xy = true_xy * tf.cast(grid_size, tf.float32) - \
            tf.cast(grid, tf.float32)
        true_wh = tf.math.log(true_wh / anchors)
        true_wh = tf.where(tf.math.is_inf(true_wh),
                           tf.zeros_like(true_wh), true_wh)

        # 4. calculate all masks
        obj_mask = tf.squeeze(true_obj, -1)
        # ignore false positive when iou is over threshold
        best_iou = tf.map_fn(
            lambda x: tf.reduce_max(broadcast_iou(x[0], tf.boolean_mask(
                x[1], tf.cast(x[2], tf.bool))), axis=-1),
            (pred_box, true_box, obj_mask),
            tf.float32)
        ignore_mask = tf.cast(best_iou < ignore_thresh, tf.float32)

        # 5. calculate all losses
        xy_loss = obj_mask * box_loss_scale * \
            tf.reduce_sum(tf.square(true_xy - pred_xy), axis=-1)
        wh_loss = obj_mask * box_loss_scale * \
            tf.reduce_sum(tf.square(true_wh - pred_wh), axis=-1)
        obj_loss = binary_crossentropy(true_obj, pred_obj)
        obj_loss = obj_mask * obj_loss + \
            (1 - obj_mask) * ignore_mask * obj_loss
        # TODO: use binary_crossentropy instead
        class_loss = obj_mask * sparse_categorical_crossentropy(
            true_class_idx, pred_class)

        # 6. sum over (batch, gridx, gridy, anchors) => (batch, 1)
        xy_loss = tf.reduce_sum(xy_loss, axis=(1, 2, 3))
        wh_loss = tf.reduce_sum(wh_loss, axis=(1, 2, 3))
        obj_loss = tf.reduce_sum(obj_loss, axis=(1, 2, 3))
        class_loss = tf.reduce_sum(class_loss, axis=(1, 2, 3))

        return xy_loss + wh_loss + obj_loss + class_loss
    return yolo_loss
