from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import os
import keras
from keras import backend as K
from keras.layers import Dense, Activation, Dropout, Flatten, Conv2D
from keras.preprocessing import image
from keras.applications.vgg19 import preprocess_input
from keras.models import Model, Sequential
import numpy as np
import matplotlib
import pandas as pd
import cv2
from keras.utils import to_categorical
from keras.layers import Dense, GlobalAveragePooling2D
import tensorflow as tf
from keras.callbacks import ModelCheckpoint
from cleverhans.attacks import FastGradientMethod
from cleverhans.loss import CrossEntropy
from cleverhans.train import train
from cleverhans.utils import AccuracyReport
from cleverhans.utils_keras import cnn_model
from cleverhans.utils_keras import KerasModelWrapper
from cleverhans.utils_tf import model_eval
from cleverhans.utils_tf import model_argmax
import functools
import tensorflow as tf
from cleverhans import initializers
from cleverhans.model import Model
#from cleverhans.picklable_model import MLP, Conv2D, ReLU, Flatten, Linear
from cleverhans.picklable_model import Softmax
import math
import logging
from tensorflow.python.platform import flags
from cleverhans.dataset import MNIST
from cleverhans.utils import AccuracyReport, set_log_level
from cleverhans.augmentation import random_horizontal_flip, random_shift
from cleverhans.dataset import CIFAR10
from cleverhans.model_zoo.all_convolutional import ModelAllConvolutional
from keras.models import load_model

from pdb import set_trace as trace

from shutil import copyfile
import imageio
from PIL import Image
import tensorflow as tf
from tensorflow.contrib.layers.python.layers import batch_norm

import os, csv, keras, math, logging, functools, cv2, sys
#from keras.applications.vgg19 import VGG19, preprocess_input
from keras.preprocessing import image
from keras.models import Model, Sequential
from keras.layers import Dense, Activation, Dropout, Flatten, Conv2D, GlobalAveragePooling2D, ZeroPadding2D, Convolution2D, MaxPooling2D
import numpy as np
import pandas as pd
from keras.utils import to_categorical
#from sklearn.preprocessing import OneHotEncoder
import tensorflow as tf
from keras.callbacks import ModelCheckpoint
from cleverhans.attacks import FastGradientMethod
from cleverhans.loss import CrossEntropy
from cleverhans.train import train
from cleverhans.utils import AccuracyReport, set_log_level
from cleverhans.utils_keras import cnn_model
from cleverhans.utils_keras import KerasModelWrapper
from cleverhans.utils_tf import model_eval, model_argmax
from cleverhans import initializers
from cleverhans.model import Model
from tensorflow.python.platform import flags
#from cleverhans.model_zoo.all_convolutional import ModelAllConvolutional
#from vgg import VGG16
#from vgg19 import VGG19
from keras.datasets import cifar10
#from sklearn.utils import class_weight
import ssl
ssl._create_default_https_context = ssl._create_unverified_context



classes = ['basophil', 'neutrophil', 'eosinophil', 'lymphocyte', 'monocyte', 'mixed']
num_classes = len(classes)
#os.environ["CUDA_VISIBLE_DEVICES"]="0"
#os.environ["TF_CPP_MIN_LOG_LEVEL"]="2"
def toOneHot(a):
        global num_classes
        b = np.zeros((a.shape[0], num_classes))
        for i in range(a.shape[0]):
                for j in range(num_classes):
                        if a[i] == classes[j]:
                                b[i][j] = 1
        return b

def del_all_flags(FLAGS):
        flags_dict = FLAGS._flags()
        keys_list = [keys for keys in flags_dict]
        for keys in keys_list:
                FLAGS.__delattr__(keys)



def lrelu(x , alpha = 0.2 , name="LeakyReLU"):
    return tf.maximum(x , alpha*x)

def conv2d(input_, output_dim,
           k_h=5, k_w=5, d_h=2, d_w=2, stddev=0.02,
           name="conv2d"):

    with tf.variable_scope(name):

        w = tf.get_variable('w', [k_h, k_w, input_.get_shape()[-1], output_dim],
                            initializer=tf.truncated_normal_initializer(stddev=stddev))
        conv = tf.nn.conv2d(input_, w, strides=[1, d_h, d_w, 1], padding='SAME')
        biases = tf.get_variable('biases', [output_dim], initializer=tf.constant_initializer(0.0))
        conv = tf.reshape(tf.nn.bias_add(conv, biases), conv.get_shape())

        return conv

def de_conv(input_, output_shape,
             k_h=5, k_w=5, d_h=2, d_w=2, stddev=0.02,
             name="deconv2d", with_w=False):

    with tf.variable_scope(name):
        # filter : [height, width, output_channels, in_channels]
        w = tf.get_variable('w', [k_h, k_w, output_shape[-1], input_.get_shape()[-1]],
                            initializer=tf.random_normal_initializer(stddev=stddev))

        try:
            deconv = tf.nn.conv2d_transpose(input_, w, output_shape=output_shape,
                                            strides=[1, d_h, d_w, 1])

        # Support for verisons of TensorFlow before 0.7.0
        except AttributeError:

            deconv = tf.nn.deconv2d(input_, w, output_shape=output_shape,
                                    strides=[1, d_h, d_w, 1])

        biases = tf.get_variable('biases', [output_shape[-1]], initializer=tf.constant_initializer(0.0))
        deconv = tf.reshape(tf.nn.bias_add(deconv, biases), deconv.get_shape())

        if with_w:

            return deconv, w, biases

        else:

            return deconv

def fully_connect(input_, output_size, scope=None, stddev=0.02, bias_start=0.0, with_w=False):
  shape = input_.get_shape().as_list()
  with tf.variable_scope(scope or "Linear"):

    matrix = tf.get_variable("Matrix", [shape[1], output_size], tf.float32,
                 tf.random_normal_initializer(stddev=stddev))
    bias = tf.get_variable("bias", [output_size],
      initializer=tf.constant_initializer(bias_start))

    if with_w:
      return tf.matmul(input_, matrix) + bias, matrix, bias
    else:

      return tf.matmul(input_, matrix) + bias

def conv_cond_concat(x, y):
    """Concatenate conditioning vector on feature map axis."""
    x_shapes = x.get_shape()
    y_shapes = y.get_shape()

    return tf.concat(3 , [x , y*tf.ones([x_shapes[0], x_shapes[1], x_shapes[2] , y_shapes[3]])])

def batch_normal(input , scope="scope" , reuse=False):
    return batch_norm(input , epsilon=1e-5, decay=0.9 , scale=True, scope=scope , reuse=reuse , updates_collections=None)

def instance_norm(x):

    epsilon = 1e-9
    mean, var = tf.nn.moments(x, [1, 2], keep_dims=True)
    return tf.div(tf.subtract(x, mean), tf.sqrt(tf.add(var, epsilon)))

# def residual(x, output_dims, kernel, strides, name_1, name_2):

#     with tf.variable_scope('residual') as scope:

#         conv1 = conv2d(x, output_dims, k_h=kernel, k_w=kernel, d_h=strides, d_w=strides, name=name_1)
#         conv2 = conv2d(tf.nn.relu(conv1), output_dims, k_h=kernel, k_w=kernel, d_h=strides, d_w=strides, name=name_2)
#         resi = x + conv2

#         return resi

# def deresidual(x, output_shape, kernel, strides, name_1, name_2):

#     with tf.variable_scope('residual_un') as scope:

#         deconv1 = de_conv(x, output_shape=output_shape, k_h=kernel, k_w=kernel, d_h=strides, d_w=strides, name=name_1)
#         deconv2 = de_conv(tf.nn.relu(deconv1), output_shape=output_shape, k_h=kernel, k_w=kernel, d_h=strides, d_w=strides, name=name_2)
#         resi = x + deconv2

#         return resi
import os
import errno
import numpy as np
import scipy
import scipy.misc
from keras.models import Model


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def get_image(image_path, image_size, is_crop=True, resize_w=64, is_grayscale=False):
    return transform(imread(image_path, is_grayscale), image_size, is_crop, resize_w)


# def transform(image, npx=64, is_crop=False, resize_w=64):
#     # npx : # of pixels width/height of image
#     if is_crop:
#         cropped_image = center_crop(image, npx, resize_w=resize_w)
#     else:
#         cropped_image = image
#         cropped_image = scipy.misc.imresize(cropped_image,
#                                             [resize_w, resize_w])
#     return np.array(cropped_image) / 127.5 - 1

def center_crop(x, crop_h , crop_w=None, resize_w=64):

    if crop_w is None:
        crop_w = crop_h
    h, w = x.shape[:2]
    j = int(round((h - crop_h)/2.))
    i = int(round((w - crop_w)/2.))
    return scipy.misc.imresize(x[j:j+crop_h, i:i+crop_w],
                               [resize_w, resize_w])


def save_images(images, size, image_path):
    return imsave(inverse_transform(images), size, image_path)

def imread(path, is_grayscale=False):
    if (is_grayscale):
        return scipy.misc.imread(path, flatten=True).astype(np.float)
    else:
        return scipy.misc.imread(path).astype(np.float)


def imsave(images, size, path):
    return scipy.misc.imsave(path, merge(images, size))

def merge(images, size):
    h, w = images.shape[1], images.shape[2]
    size1 = np.int(h * size[0])
    size2 = np.int(w * size[1])
    img = np.zeros((size1,size2, 3))
    for idx, image in enumerate(images):
        i = idx % size[1]
        j = idx // size[1]
        img[np.int(j * h):np.int(j * h + h), np.int(i * w): np.int(i * w + w), :] = image

    return img



# def inverse_transform(image):
#     return ((image + 1) * 127.5).astype(np.uint8)



import tensorflow as tf

from cleverhans import initializers
from cleverhans.serial import NoRefModel



from keras.utils.np_utils import to_categorical 
import PIL
import numpy as np
import scipy
from tensorflow.python.framework.ops import convert_to_tensor
import os
TINY = 1e-8
d_scale_factor = 0.25
g_scale_factor =  1 - 0.75/2
import csv

def getAcc(pred, next_y_images):
    global num_classes
    acc = np.zeros([num_classes])
    Tc = np.ones([num_classes])
    for i in range(len(pred)):
        Tc[np.argmax(next_y_images[i])] = Tc[np.argmax(next_y_images[i])] + 1
        if (np.argmax(next_y_images[i]) == np.argmax(pred[i])):
            acc[np.argmax(next_y_images[i])] = acc[np.argmax(next_y_images[i])] + 1
    print(100*np.sum(acc)/(np.sum(Tc)-num_classes))
    return 100*acc/Tc,100*np.sum(acc)/(np.sum(Tc)-num_classes)
class ModelAllConvolutional(NoRefModel):
  """
  A simple model that uses only convolution and downsampling---no batch norm or other techniques that can complicate
  adversarial training.
  """
  def __init__(self, scope, nb_classes, nb_filters, input_shape, **kwargs):
    del kwargs
    NoRefModel.__init__(self, scope, nb_classes, locals())
    self.nb_filters = nb_filters
    self.input_shape = input_shape

    # Do a dummy run of fprop to create the variables from the start
    self.fprop(tf.placeholder(tf.float32, [32] + input_shape))
    # Put a reference to the params in self so that the params get pickled
    self.params = self.get_params()

  def fprop(self, x, **kwargs):
    del kwargs
    conv_args = dict(
        activation=tf.nn.leaky_relu,
        kernel_initializer=initializers.HeReLuNormalInitializer,
        kernel_size=3,
        padding='same')
    y = x

    with tf.variable_scope(self.scope, reuse=tf.AUTO_REUSE):
      log_resolution = int(round(
          math.log(self.input_shape[0]) / math.log(2)))
      for scale in range(log_resolution - 2):
        y = tf.layers.conv2d(y, self.nb_filters << scale, **conv_args)
        y = tf.layers.conv2d(y, self.nb_filters << (scale + 1), **conv_args)
        y = tf.layers.average_pooling2d(y, 2, 2)
      y = tf.layers.conv2d(y, self.nb_classes, **conv_args)
      logits = tf.reduce_mean(y, [1, 2])
      return {self.O_LOGITS: logits,
              self.O_PROBS: tf.nn.softmax(logits=logits)}


class ModelAllConvolutional1(NoRefModel):
  """
  A simple model that uses only convolution and downsampling---no batch norm or other techniques that can complicate
  adversarial training.
  """
  def __init__(self, scope, nb_classes, nb_filters, input_shape, **kwargs):
    del kwargs
    NoRefModel.__init__(self, scope, nb_classes, locals())
    self.nb_filters = nb_filters
    self.input_shape = input_shape

    # Do a dummy run of fprop to create the variables from the start
    self.fprop(tf.placeholder(tf.float32, [32] + input_shape))
    # Put a reference to the params in self so that the params get pickled
    self.params = self.get_params()

  def fprop(self, x, **kwargs):
    del kwargs
    conv_args = dict(
        activation=tf.nn.leaky_relu,
        kernel_initializer=initializers.HeReLuNormalInitializer,
        kernel_size=3,
        padding='same')
    y = x

    with tf.variable_scope(self.scope, reuse=tf.AUTO_REUSE):
      log_resolution = int(round(
          math.log(self.input_shape[0]) / math.log(2)))
      for scale in range(log_resolution - 4):
        y = tf.layers.conv2d(y, self.nb_filters << scale, **conv_args)
        y = tf.layers.conv2d(y, self.nb_filters << (scale + 1), **conv_args)
        y = tf.layers.average_pooling2d(y, 2, 2)
      conv = y
      scale = log_resolution - 4
      y = tf.layers.conv2d(y, self.nb_filters << scale, **conv_args)
      y = tf.layers.conv2d(y, self.nb_filters << (scale + 1), **conv_args)
      y = tf.layers.average_pooling2d(y, 2, 2)


      scale = log_resolution - 3
      y = tf.layers.conv2d(y, self.nb_filters << scale, **conv_args)
      y = tf.layers.conv2d(y, self.nb_filters << (scale + 1), **conv_args)
      y = tf.layers.average_pooling2d(y, 2, 2)
      y = tf.layers.conv2d(y, self.nb_classes, **conv_args)

      logits = tf.reduce_mean(y, [1, 2])
      return {self.O_LOGITS: conv,
              self.O_PROBS: tf.nn.softmax(logits=logits)}



class vaegan(object):

    #build model
    def __init__(self, batch_size, max_iters, repeat, model_path, latent_dim, sample_path, log_dir, learnrate_init):

        self.batch_size = batch_size
        self.max_iters = max_iters
        self.repeat_num = repeat
        self.saved_model_path = model_path

        self.latent_dim = latent_dim
        self.sample_path = sample_path
        self.log_dir = log_dir
        self.learn_rate_init = learnrate_init

        self.log_vars = []

        self.channel = 3
        self.output_size = 128

        self.x_input = tf.placeholder(tf.float32, [self.batch_size, self.output_size, self.output_size, 3])
        self.x_true = tf.placeholder(tf.float32, [self.batch_size, self.output_size, self.output_size, self.channel])



        self.labels = tf.placeholder(tf.float32, [self.batch_size, num_classes])


        self.ep1 = tf.random_normal(shape=[self.batch_size, self.latent_dim])
        self.zp1 = tf.random_normal(shape=[self.batch_size, self.latent_dim])

        self.ep2 = tf.random_normal(shape=[self.batch_size, self.latent_dim])
        self.zp2 = tf.random_normal(shape=[self.batch_size, self.latent_dim])
        self.keep_prob = tf.placeholder_with_default(1.0, shape=())
 
        print('Data Loading Begins')
        
        y_train=[]
        x_train1=[]
        main_directory = 'WBC-Classification-UDA/Main Dataset/'
        for dirs in os.listdir(main_directory):
            if (dirs == '.ipynb_checkpoints'):
              continue
            if (dirs == 'Thumbs.db'):
              continue
            for files in os.listdir(main_directory + dirs)[0:int(0.7*len(os.listdir(main_directory + dirs)))]:
                if files != "Thumbs.db":
                    y_train.append(int(dirs))
                    img = Image.open(main_directory + dirs + '/' + files)
                    img_resized = img.resize((128, 128))
                    x_train1.append(np.array(img_resized))
        
        #x_train1 =np.asarray(x_train1)/255.0
        
        cam3_train_data=[]
        cam3_train_label=[]
        
        l=list(range(0,len(y_train)))
        l=np.asarray(l)
        np.random.shuffle(l)
        for i in l:
            cam3_train_data.append(x_train1[i])
            cam3_train_label.append(y_train[i])
               
        x_train1=cam3_train_data
        y_train=cam3_train_label
        
        x_train1 = np.asarray(x_train1)/127.5
        x_train1 =x_train1 - 1.
        y_train = np.asarray(y_train)
        #y_train = toOneHot(y_train)
        y_train= to_categorical(y_train, num_classes=num_classes)
#         x_train1 = np.load( '/home/vinay/projects/Sigtuple/CreateData/DataAugmentation/X_Train.npy').astype('float32')
#         y_train = np.load( '/home/vinay/projects/Sigtuple/CreateData/DataAugmentation/Y_Train.npy')
#         x_train1_1 = np.load('/home/vinay/projects/Sigtuple/CreateData/DataAugmentation/X_Test.npy').astype('float32')
#         y_train_1 = np.load('/home/vinay/projects/Sigtuple/CreateData/DataAugmentation/Y_Test.npy')

#         x_train1_2 = np.load( '/home/vinay/projects/Sigtuple/CameraInvariance/Cam3Classifier/Data_Augmentation/X_Train_extra.npy').astype('float32')
#         y_train_2 = np.load( '/home/vinay/projects/Sigtuple/CameraInvariance/Cam3Classifier/Data_Augmentation/Y_Train_extra.npy')

#         x_train1 = np.append(x_train1, x_train1_2,axis =0)
#         y_train = np.append(y_train, y_train_2,axis =0)


#         x_train1 = np.concatenate((x_train1, x_train1_1), axis=0)
#         y_train  = np.concatenate((y_train, y_train_1), axis=0)


        x_test1_cam3 = []
        y_test_cam3 = []
        
        for dirs in os.listdir(main_directory):
            if (dirs == '.ipynb_checkpoints'):
              continue
            if (dirs == 'Thumbs.db'):
              continue
            for files in os.listdir(main_directory + dirs)[int(0.7*len(os.listdir(main_directory + dirs))):-1]:
                if files != "Thumbs.db":
                    y_test_cam3.append(int(dirs))
                    img = Image.open(main_directory + dirs + '/' + files)
                    img_resized = img.resize((128, 128))
                    x_test1_cam3.append(np.array(img_resized))
         
        cam3_test_data=[]
        cam3_test_label=[]
        
        l=list(range(0,len(y_test_cam3)))
        l=np.asarray(l)
        np.random.shuffle(l)
        for i in l:
            cam3_test_data.append(x_test1_cam3[i])
            cam3_test_label.append(y_test_cam3[i])
            
        x_test1_cam3 = cam3_test_data
        y_test_cam3 = cam3_test_label
         
        y_test_cam3= to_categorical(y_test_cam3, num_classes=num_classes) 
        #y_test_cam3 = toOneHot(np.asarray(y_test_cam3))
        #x_test1_cam3=np.asarray(x_test1_cam3)/255.0
        x_test1_cam3 = np.asarray(x_test1_cam3)/127.5
        x_test1_cam3 =x_test1_cam3 - 1.
        
        x_test1=[]
        y_test =[]
        
        for dirs in os.listdir(main_directory):
            if (dirs == '.ipynb_checkpoints'):
              continue
            if (dirs == 'Thumbs.db'):
              continue
            for files in os.listdir(main_directory + dirs)[int(0.7*len(os.listdir(main_directory + dirs))):-1]:
                y_test.append(int(dirs))
                img = Image.open(main_directory + dirs + '/' + files)
                img_resized = img.resize((128, 128))
                x_test1.append(np.array(img_resized))
                
#         x_test1 = np.load('/home/vinay/projects/Sigtuple/CreateData/cam2_images.npy').astype('float32')/255
#         y_test = np.load('/home/vinay/projects/Sigtuple/CreateData/cam2_labels.npy')

        cam2_data=[]
        cam2_label=[]

        l=list(range(0,len(y_test)))
        l=np.asarray(l)
        np.random.shuffle(l)
        for i in l:
            cam2_data.append(x_test1[i])
            cam2_label.append(y_test[i])
            
        x_test1 = cam2_data
        y_test = cam2_label
        
        y_test= to_categorical(y_test, num_classes=num_classes)
        #y_test = toOneHot(np.asarray(y_test))
       # x_test1=np.asarray(x_test1)/255.0
        x_test1 = np.asarray(x_test1)/127.5
        x_test1 =x_test1 - 1.

#         x_test1_cam3 = np.load('/home/vinay/projects/Sigtuple/CreateData/cam3_images.npy').astype('float32')/255
#         y_test_cam3 = np.load('/home/vinay/projects/Sigtuple/CreateData/cam3_labels.npy')
#         y_test_cam3 = toOneHot(y_test_cam3)

        #print(x_train1.shape, y_train.shape)
        #print(x_test1.shape, y_test.shape)
        #x_train = np.zeros([x_train1.shape[0], self.output_size,self.output_size,self.channel])
        #x_test = np.zeros([x_test1.shape[0], self.output_size,self.output_size,self.channel])
        #x_test_cam3 = np.zeros([x_test1_cam3.shape[0], self.output_size,self.output_size,self.channel])

#         x_train[:,:,:,0] = x_train1[:,:,:,2]
#         x_train[:,:,:,1] = x_train1[:,:,:,1]
#         x_train[:,:,:,2] = x_train1[:,:,:,0]

#         x_test[:,:,:,0] = x_test1[:,:,:,2]
#         x_test[:,:,:,1] = x_test1[:,:,:,1]
#         x_test[:,:,:,2] = x_test1[:,:,:,0]

#         x_test_cam3[:,:,:,0] = x_test1_cam3[:,:,:,2]
#         x_test_cam3[:,:,:,1] = x_test1_cam3[:,:,:,1]
#         x_test_cam3[:,:,:,2] = x_test1_cam3[:,:,:,0]

        x_train = np.float32(x_train1).reshape([-1,self.output_size,self.output_size,self.channel])
        x_test = np.float32(x_test1).reshape([-1,self.output_size,self.output_size,self.channel])
        x_test_cam3 = np.float32(x_test1_cam3).reshape([-1,self.output_size,self.output_size,self.channel])

        print(x_train.shape, y_train.shape)
        print(x_test.shape, y_test.shape)
        print(x_test_cam3.shape, y_test_cam3.shape)
        print(np.amin(x_train), np.amin( x_test ), np.amin(x_test_cam3))
        print(np.amax(x_train), np.amax( x_test ), np.amax(x_test_cam3))


        TrainDataSize = x_train.shape[0]
        TestDataSize = x_test.shape[0]
        self.TrainDataSize = TrainDataSize
        self.TestDataSize = TestDataSize
        self.TestDataSize_cam3 = x_test_cam3.shape[0]


        self.X_Real_Test = x_test
        self.X_Real_Train = x_train
        self.X_Real_Test_cam3 = x_test_cam3       
        self.Y_train = y_train
        self.Y_test = y_test
        self.Y_test_cam3 = y_test_cam3


#         self.X_Real_Train =  self.X_Real_Train*2 - 1
#         self.X_Real_Test  =  self.X_Real_Test*2 - 1
#         self.X_Real_Test_cam3  =  self.X_Real_Test_cam3*2 - 1

        print('Max', np.max(self.X_Real_Train))
        print('Min', np.min(self.X_Real_Train))

        print('Data Loading Completed')





    def build_model_vaegan(self):

        self.z1_mean, self.z1_sigm = self.Encode1(self.x_input)
        self.z1_x = tf.add( self.z1_mean, tf.sqrt(tf.exp(self.z1_sigm))*self.ep1)
        self.x_input_sobel = tf.image.sobel_edges(self.x_input)
        self.x_input_sobel = tf.reshape(self.x_input_sobel, [64,128,128,6])
        self.x_out = self.generate1(self.x_input_sobel, self.z1_x, reuse=False)

        self.x_filt2 = self.generate1(self.x_input_sobel, self.z1_mean, reuse=True)

        self.model_classifier_logits = ModelAllConvolutional('model1', num_classes, 64, input_shape=[self.output_size,self.output_size,self.channel])
        self.model_classifier_percept = ModelAllConvolutional1('model2', num_classes, 64, input_shape=[self.output_size,self.output_size,self.channel])
        #tanh o/p -1 to 1
        self.logits_x_true = self.model_classifier_logits.get_logits((self.x_true+1)*0.5)
        self.percept_x_true = self.model_classifier_percept.get_logits((self.x_true+1)*0.5)
        #self.pred_x_true = tf.nn.softmax(self.logits_x_true)
        self.pred_x_true = self.model_classifier_percept.get_probs((self.x_true+1)*0.5)


        self.logits_x_out = self.model_classifier_logits.get_logits((self.x_out+1)*0.5)
        self.percept_x_out = self.model_classifier_percept.get_logits((self.x_out+1)*0.5)
        self.pred_x_out = tf.nn.softmax(self.logits_x_out)


        self.logits_x_filt2 = self.model_classifier_logits.get_logits((self.x_filt2+1)*0.5)
        self.pred_x_filt2   = tf.nn.softmax(self.logits_x_filt2)



        self.cl_loss_x_true =  tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits = self.logits_x_true, labels = self.labels))
        self.cl_loss_x_out  =  tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits = self.logits_x_out , labels = self.labels))
        self.cl_loss_x_true  =  tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits = self.logits_x_true, labels = self.labels))



        self.kl1_loss = self.KL_loss(self.z1_mean, self.z1_sigm)/(self.latent_dim*self.batch_size)


        self.Loss_vae1_pixel = tf.reduce_mean(tf.square(tf.subtract(self.x_out, self.x_true))) +  tf.reduce_mean(tf.abs(tf.subtract(self.x_out, self.x_true))) 
        self.Loss_vae1_percept = tf.reduce_mean(tf.square(tf.subtract(self.percept_x_out, self.percept_x_true)))
        self.Loss_vae1_logits = tf.reduce_mean(tf.square(tf.subtract(self.logits_x_out, self.logits_x_true)))



        #For encode
        self.encode1_loss = 1*self.kl1_loss + 10*self.Loss_vae1_pixel  +  0*self.cl_loss_x_out + 0*self.Loss_vae1_logits + 1000*self.Loss_vae1_percept

        #for Gen
        self.G1_loss =  10*self.Loss_vae1_pixel +    0*self.cl_loss_x_out + 0*self.Loss_vae1_logits + 1000*self.Loss_vae1_percept


        t_vars = tf.trainable_variables()

        self.log_vars.append(("encode1_loss", self.encode1_loss))
        self.log_vars.append(("generator1_loss", self.G1_loss))



        self.g1_vars = [var for var in t_vars if 'VAE_gen1' in var.name]
        self.e1_vars = [var for var in t_vars if 'VAE_e1_' in var.name]


        self.saver = tf.train.Saver()
        for k, v in self.log_vars:
            tf.summary.scalar(k, v)

        print('Model is Built')





    #do train
    def train(self):

        global_step = tf.Variable(0, trainable=False)
        add_global = global_step.assign_add(1)
        new_learning_rate = tf.train.exponential_decay(self.learn_rate_init, global_step=global_step, decay_steps=10000,
                                                   decay_rate=0.98)

        #for G1
        trainer_G1 = tf.train.RMSPropOptimizer(learning_rate=new_learning_rate)
        #trainer_G1 = tf.train.RMSPropOptimizer(learning_rate=self.learn_rate_init)
        #trainer_G1 = tf.train.AdamOptimizer(learning_rate=new_learning_rate)
        gradients_G1 = trainer_G1.compute_gradients(self.G1_loss, var_list=self.g1_vars)
        opti_G1 = trainer_G1.apply_gradients(gradients_G1)



        #for E1
        trainer_E1 = tf.train.RMSPropOptimizer(learning_rate=new_learning_rate)
        #trainer_E1 = tf.train.RMSPropOptimizer(learning_rate=self.learn_rate_init)
        #trainer_E1 = tf.train.AdamOptimizer(learning_rate=new_learning_rate)
        gradients_E1 = trainer_E1.compute_gradients(self.encode1_loss, var_list=self.e1_vars)
        opti_E1 = trainer_E1.apply_gradients(gradients_E1)



        init = tf.global_variables_initializer()
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        with tf.Session(config=config) as sess:

            #This one I comemnt
            #changed restoring of weights. 
            #ckpt = tf.train.get_checkpoint_state('WBC-Classification-UDA/checkpoint')
            #ckpt_path = ckpt.model_checkpoint_path
            sess.run(init)
            #self.saver.restore(sess , self.saved_model_path)
            #print(tf.trainable_variables(),'tf.trainable_variables()')
            #saver = tf.train.Saver([var for var in tf.trainable_variables() if var.name.startswith('model1')])
            #print(ckpt_path)
            #saver.restore(sess, ckpt_path)
            
            ##self.saver.save(sess , self.saved_model_path)
            
            #This one I comment
            # print('Creating a Replica of s1 onto s2')
            # s1_vars1 = [var.name for var in tf.trainable_variables() if 'model1' in var.name]
            # s2_vars1 = [var for var in tf.trainable_variables() if 'model2' in var.name]
            # dictionary = {}
            # for i in range(len(s2_vars1)):
            #     dictionary[s1_vars1[i][0:-2]] = s2_vars1[i]
            # saver_new = tf.train.Saver(var_list=dictionary)
            
            
            
            #saver_new.restore(sess, ckpt_path)


            ##self.saver.save(sess , ckpt.model_checkpoint_path)


            print('******************')
            print(' ')
            print(' ')
            print('Plain VAE Training Begins')
            print(' ')
            print(' ')
            print('******************')

            step = 0
            g_acc=87.0
            batchNum = 0
            step=0

            while step <= 100000:
                next_x_images = self.X_Real_Train[batchNum*self.batch_size:(batchNum+1)*self.batch_size]
                next_y_images = self.Y_train[batchNum*self.batch_size:(batchNum+1)*self.batch_size]
                
                if next_x_images.shape[0] != 64 or next_y_images.shape[0] != 64:
                    continue
                
                batchNum = batchNum +1
                #print(batchNum*self.batch_size)
                if(((batchNum+1)%170)==0):
                    idx = np.random.permutation(len(self.X_Real_Train))
                    self.X_Real_Train,self.Y_train = self.X_Real_Train[idx], self.Y_train[idx]
                    batchNum = 0
                    print('data exhausted')
                    #print(idx)
                    #print(self.X_Real_Train.shape, self.Y_train.shape)
                #print(batchNum)
                #print(next_y_images)
                fd ={self.keep_prob:1, self.x_input: next_x_images,  self.x_true: next_x_images, self.labels: next_y_images}
                sess.run(opti_E1, feed_dict=fd)
                sess.run(opti_G1, feed_dict=fd)



                new_learn_rate = sess.run(new_learning_rate)

                if new_learn_rate > 0.00005:
                    sess.run(add_global)

                
                if np.mod(step , 100) == 0 and step != 0:
#                     for iter in range(200):
#                         print('step', step)
                    #print('model saved: ', self.saved_model_path)
                    #self.saver.save(sess , self.saved_model_path, global_step=step)

                    print('lr:', new_learn_rate)
                    k1, e1, l11,  l12, l13, cl, g1 = sess.run([self.kl1_loss , self.encode1_loss,self.Loss_vae1_pixel,self.Loss_vae1_percept, self.Loss_vae1_logits,self.cl_loss_x_out,self.G1_loss],feed_dict=fd)
                    print('E1_loss_KL_Loss: ',k1)
                    print('E1_loss_Total: ', e1)

                    print('G1_loss_MSE: ', l11,  10*l11)
                    print('G1_loss_Percept: ', l12,  0*l12)
                    print('G1_loss_Logits: ', l13,  0*l13)
                    print('G1_loss_CL: ', cl, 1*cl)
                    print('G1_loss_Total: ', g1)

                    Preddiction = np.zeros([self.TestDataSize_cam3,num_classes])
                    for i in range(np.int(self.TestDataSize_cam3/self.batch_size)):
                        next_x_images = self.X_Real_Test_cam3[i*self.batch_size:(i+1)*self.batch_size]
                        pred = sess.run(self.pred_x_filt2, feed_dict={self.x_input: next_x_images, self.keep_prob:1})
                        Preddiction[i*self.batch_size:(i+1)*self.batch_size] = pred.reshape([64,num_classes])
                    x_filt = sess.run(self.x_filt2, feed_dict={self.x_input: next_x_images, self.keep_prob:1})
                    x_filt_percept = sess.run(self.percept_x_out, feed_dict={self.x_input: next_x_images, self.keep_prob:1})
                    print('shape:', x_filt_percept.shape)
                    if (step == 100):
                        np.save('Data/x_cam3_test.npy',next_x_images)
                    name = 'Data/x_filt__' + str(step) + '_.npy' 
                    np.save(name,x_filt)
#                     print('Full  Filtered Real Train  Example  Acc = ',getAcc(Preddiction[0:150*64], self.Y_test_cam3[0:150*64]))
#                     print('Full  Filtered Real Test  Example  Acc = ',getAcc(Preddiction[150*64:], self.Y_test_cam3[150*64:]))
                    accs,l_acc = getAcc(Preddiction, self.Y_test_cam3)
                    print('Full  Filtered Real Test  Example  Acc = ',accs,l_acc)
                    if(l_acc>g_acc):
                        print('model saved: ', 'WBC-Classification-UDA/models/model.ckpt')
                        self.saver.save(sess , 'WBC-Classification-UDA/models/model.cpkt', global_step=step)
                        g_acc= l_acc

                    Preddiction = np.zeros([self.TrainDataSize,num_classes])
                    for i in range(np.int(self.TrainDataSize/self.batch_size)):
                        next_x_images = self.X_Real_Train[i*self.batch_size:(i+1)*self.batch_size]
                        pred = sess.run(self.pred_x_filt2, feed_dict={self.x_input: next_x_images, self.keep_prob:1})
                        Preddiction[i*self.batch_size:(i+1)*self.batch_size] = pred.reshape([64,num_classes])
                    print('Full  Filtered Real Train  Example  Acc = ',getAcc(Preddiction, self.Y_train))
                    if (step == 100):
                        np.save('Data/x_cam3_train.npy',next_x_images)

                    Preddiction = np.zeros([self.TestDataSize,num_classes])
                    for i in range(np.int(self.TestDataSize/self.batch_size)):
                        next_x_images = self.X_Real_Test[i*self.batch_size:(i+1)*self.batch_size]
                        pred = sess.run(self.pred_x_filt2, feed_dict={self.x_input: next_x_images, self.keep_prob:1})
                        Preddiction[i*self.batch_size:(i+1)*self.batch_size] = pred.reshape([64,num_classes])

                    print('Full  Filtered Real Cam2 Example  Acc = ',getAcc(Preddiction, self.Y_test))
                    if (step == 100):
                        np.save('Data/x_cam2.npy',next_x_images)

                    Preddiction = np.zeros([self.TestDataSize,num_classes])
                    for i in range(np.int(self.TestDataSize/self.batch_size)):
                        next_x_images = self.X_Real_Test[i*self.batch_size:(i+1)*self.batch_size]
                        pred = sess.run(self.pred_x_true, feed_dict={self.x_true: next_x_images, self.keep_prob:1})
                        Preddiction[i*self.batch_size:(i+1)*self.batch_size] = pred.reshape([64,num_classes])
                    print('Full Real Cam2 Example  Acc = ',getAcc(Preddiction, self.Y_test))

                    Preddiction = np.zeros([self.TestDataSize_cam3,num_classes])
                    for i in range(np.int(self.TestDataSize_cam3/self.batch_size)):
                        next_x_images = self.X_Real_Test_cam3[i*self.batch_size:(i+1)*self.batch_size]
                        pred = sess.run(self.pred_x_true, feed_dict={self.x_true: next_x_images, self.keep_prob:1})
                        Preddiction[i*self.batch_size:(i+1)*self.batch_size] = pred.reshape([64,num_classes])
                        
                    print('Full  Real Test  Example  Acc = ',getAcc(Preddiction, self.Y_test_cam3))
                    
                    Preddiction = np.zeros([self.TrainDataSize,num_classes])
                    for i in range(np.int(self.TrainDataSize/self.batch_size)):
                        next_x_images = self.X_Real_Train[i*self.batch_size:(i+1)*self.batch_size]
                        pred = sess.run(self.pred_x_true, feed_dict={self.x_true: next_x_images, self.keep_prob:1})
                        Preddiction[i*self.batch_size:(i+1)*self.batch_size] = pred.reshape([64,num_classes])
                        
                    print('Full  Real Train Example  Acc = ',getAcc(Preddiction, self.Y_train))
                    
#                     print('Full  Filtered Real Train  Example  Acc = ',getAcc(Preddiction[0:150*64], self.Y_test_cam3[0:150*64]))
#                     print('Full  Filtered Real Test  Example  Acc = ',getAcc(Preddiction[150*64:], self.Y_test_cam3[150*64:]))


                step += 1

    def generate1(self, edge, z_var, reuse=False):

        with tf.variable_scope('generator1') as scope:

            if reuse == True:
                scope.reuse_variables()

            d1 = lrelu(fully_connect(z_var , output_size=64*4*4, scope='VAE_gen1_fully1'))
            d2 = lrelu(fully_connect(d1 , output_size=128*4*4, scope='VAE_gen1_fully2'))
            d3 = tf.reshape(d2, [self.batch_size, 4, 4, 128])
            d4 = lrelu(de_conv(d3, output_shape=[self.batch_size, 8, 8, 128],  k_h=3, k_w=3,name='VAE_gen1_deconv1'))
            d5 = lrelu(de_conv(d4, output_shape=[self.batch_size, 16, 16, 128], k_h=3, k_w=3,name='VAE_gen1_deconv2'))
            d6 = lrelu(de_conv(d5, output_shape=[self.batch_size, 32, 32, 128], k_h=3, k_w=3,name='VAE_gen1_deconv3'))
            d7 = lrelu(de_conv(d6, output_shape=[self.batch_size, 64, 64, 128], k_h=3, k_w=3,name='VAE_gen1_deconv4'))
            d8 = de_conv(d7, output_shape=[self.batch_size, 128, 128, 3] , k_h=3, k_w=3, name='VAE_gen1_deconv5')
            d9 = tf.nn.tanh(d8)
            d10 = tf.concat([d9, edge], 3) 
            conv1 = lrelu(conv2d(d10, output_dim=128, k_h=3, k_w=3,  d_h=1, d_w=1,name='VAE_gen1_c1'))
            conv2 = lrelu(conv2d(conv1, output_dim=128,  k_h=3, k_w=3, d_h=1, d_w=1,name='VAE_gen1_c2'))
            conv3 = conv2d(conv2, output_dim=3,  k_h=3, k_w=3, d_h=1, d_w=1,name='VAE_gen1_c3')


            return tf.nn.tanh(conv3)


    def Encode1(self, x, reuse=False):

        with tf.variable_scope('encode1') as scope:

            if reuse == True:
                scope.reuse_variables()
            conv1 = lrelu(conv2d(x, output_dim=128, k_h=3, k_w=3, name='VAE_e1_c1'))
            conv2 = lrelu(conv2d(conv1, output_dim=128,  k_h=3, k_w=3,name='VAE_e1_c2'))
            conv3 = lrelu(conv2d(conv2, output_dim=128,  k_h=3, k_w=3,name='VAE_e1_c3'))
            conv4 = lrelu(conv2d(conv3, output_dim=128,  k_h=3, k_w=3,name='VAE_e1_c4'))
            conv5 = lrelu(conv2d(conv4, output_dim=128,  k_h=3, k_w=3,name='VAE_e1_c5'))
            conv6 = tf.reshape(conv5, [self.batch_size, 128 * 4 * 4])
            fc1   = lrelu(fully_connect(conv6, output_size= 64*4*4, scope='VAE_e1_f1'))
            z_mean  = fully_connect(fc1, output_size=self.latent_dim, scope='VAE_e1_f2')
            z_sigma = fully_connect(fc1, output_size=self.latent_dim, scope='VAE_e1_f3')
            return z_mean, z_sigma


    def KL_loss(self, mu, log_var):
        return -0.5 * tf.reduce_sum(1 + log_var - tf.pow(mu, 2) - tf.exp(log_var))

    def sample_z(self, mu, log_var):
        eps = tf.random_normal(shape=tf.shape(mu))
        return mu + tf.exp(log_var / 2) * eps


    def NLLNormal(self, pred, target):

        c = -0.5 * tf.log(2 * np.pi)
        multiplier = 1.0 / (2.0 * 1)
        tmp = tf.square(pred - target)
        tmp *= -multiplier
        tmp += c

        return tmp


flags = tf.app.flags

flags.DEFINE_integer("batch_size" , 64, "batch size")
flags.DEFINE_integer("max_iters" , 10000, "the maxmization epoch")
flags.DEFINE_integer("latent_dim" , 64, "the dim of latent code")
flags.DEFINE_float("learn_rate_init" , 0.0001, "the init of learn rate")
flags.DEFINE_integer("repeat", 10000, "the numbers of repeat for your datasets")
flags.DEFINE_string("path", '/home/?/data/', "for example, '/home/jack/data/' is the directory of your celebA data")
flags.DEFINE_integer("op", 0, "Training or Test")

FLAGS = flags.FLAGS
FLAGS.op = 0

if (1):
    path123 = './'
    root_log_dir = path123 + "WBC-Classification-UDA/log"
    vaegan_checkpoint_dir =  "WBC-Classification-UDA/checkpoint"
    sample_path =  path123 + "  sample"


    model_path = vaegan_checkpoint_dir

    batch_size = FLAGS.batch_size
    max_iters = FLAGS.max_iters
    latent_dim = FLAGS.latent_dim
    data_repeat = FLAGS.repeat

    learn_rate_init = FLAGS.learn_rate_init
    #learn_rate_init= 9e-5
    vaeGan = vaegan(batch_size= batch_size, max_iters= max_iters, repeat = data_repeat,
                      model_path= model_path, latent_dim= latent_dim,
                      sample_path= sample_path , log_dir= root_log_dir , learnrate_init= learn_rate_init)

    vaeGan.build_model_vaegan()
    vaeGan.train()