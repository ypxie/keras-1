# -*- coding: utf-8 -*-
from __future__ import absolute_import

from .. import backend as K
from .. import activations, initializations, regularizers, constraints
from ..engine import Layer, InputSpec
from ..utils.np_utils import conv_output_length, conv_input_length

# imports for backwards namespace compatibility
from .pooling import AveragePooling1D, AveragePooling2D, AveragePooling3D
from .pooling import MaxPooling1D, MaxPooling2D, MaxPooling3D

class Convolution1D(Layer):
    '''Convolution operator for filtering neighborhoods of one-dimensional inputs.
    When using this layer as the first layer in a model,
    either provide the keyword argument `input_dim`
    (int, e.g. 128 for sequences of 128-dimensional vectors),
    or `input_shape` (tuple of integers, e.g. (10, 128) for sequences
    of 10 vectors of 128-dimensional vectors).

    # Example

    ```python
        # apply a convolution 1d of length 3 to a sequence with 10 timesteps,
        # with 64 output filters
        model = Sequential()
        model.add(Convolution1D(64, 3, border_mode='same', input_shape=(10, 32)))
        # now model.output_shape == (None, 10, 64)

        # add a new conv1d on top
        model.add(Convolution1D(32, 3, border_mode='same'))
        # now model.output_shape == (None, 10, 32)
    ```

    # Arguments
        nb_filter: Number of convolution kernels to use
            (dimensionality of the output).
        filter_length: The extension (spatial or temporal) of each filter.
        init: name of initialization function for the weights of the layer
            (see [initializations](../initializations.md)),
            or alternatively, Theano function to use for weights initialization.
            This parameter is only relevant if you don't pass a `weights` argument.
        activation: name of activation function to use
            (see [activations](../activations.md)),
            or alternatively, elementwise Theano function.
            If you don't specify anything, no activation is applied
            (ie. "linear" activation: a(x) = x).
        weights: list of numpy arrays to set as initial weights.
        border_mode: 'valid', 'same' or 'full'. ('full' requires the Theano backend.)
        subsample_length: factor by which to subsample output.
        W_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the main weights matrix.
        b_regularizer: instance of [WeightRegularizer](../regularizers.md),
            applied to the bias.
        activity_regularizer: instance of [ActivityRegularizer](../regularizers.md),
            applied to the network output.
        W_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the main weights matrix.
        b_constraint: instance of the [constraints](../constraints.md) module,
            applied to the bias.
        bias: whether to include a bias
            (i.e. make the layer affine rather than linear).
        input_dim: Number of channels/dimensions in the input.
            Either this argument or the keyword argument `input_shape`must be
            provided when using this layer as the first layer in a model.
        input_length: Length of input sequences, when it is constant.
            This argument is required if you are going to connect
            `Flatten` then `Dense` layers upstream
            (without it, the shape of the dense outputs cannot be computed).

    # Input shape
        3D tensor with shape: `(samples, steps, input_dim)`.

    # Output shape
        3D tensor with shape: `(samples, new_steps, nb_filter)`.
        `steps` value might have changed due to padding.
    '''
    def __init__(self, nb_filter, filter_length,
                 init='glorot_uniform', activation=None, weights=None,
                 border_mode='valid', subsample_length=1,
                 W_regularizer=None, b_regularizer=None, activity_regularizer=None,
                 W_constraint=None, b_constraint=None,
                 bias=True, input_dim=None, input_length=None, **kwargs):

        if border_mode not in {'valid', 'same', 'full'}:
            raise ValueError('Invalid border mode for Convolution1D:', border_mode)
        self.nb_filter = nb_filter
        self.filter_length = filter_length
        self.init = initializations.get(init, dim_ordering='th')
        self.activation = activations.get(activation)
        self.border_mode = border_mode
        self.subsample_length = subsample_length

        self.subsample = (subsample_length, 1)

        self.W_regularizer = regularizers.get(W_regularizer)
        self.b_regularizer = regularizers.get(b_regularizer)
        self.activity_regularizer = regularizers.get(activity_regularizer)

        self.W_constraint = constraints.get(W_constraint)
        self.b_constraint = constraints.get(b_constraint)

        self.bias = bias
        self.input_spec = [InputSpec(ndim=3)]
        self.initial_weights = weights
        self.input_dim = input_dim
        self.input_length = input_length
        if self.input_dim:
            kwargs['input_shape'] = (self.input_length, self.input_dim)
        super(Convolution1D, self).__init__(**kwargs)

    def build(self, input_shape):
        input_dim = input_shape[2]
        self.W_shape = (self.filter_length, 1, input_dim, self.nb_filter)

        self.W = self.add_weight(self.W_shape,
                                 initializer=self.init,
                                 name='{}_W'.format(self.name),
                                 regularizer=self.W_regularizer,
                                 constraint=self.W_constraint)
        if self.bias:
            self.b = self.add_weight((self.nb_filter,),
                                     initializer='zero',
                                     name='{}_b'.format(self.name),
                                     regularizer=self.b_regularizer,
                                     constraint=self.b_constraint)
        else:
            self.b = None

        if self.initial_weights is not None:
            self.set_weights(self.initial_weights)
            del self.initial_weights
        self.built = True

    def get_output_shape_for(self, input_shape):
        length = conv_output_length(input_shape[1],
                                    self.filter_length,
                                    self.border_mode,
                                    self.subsample[0])
        return (input_shape[0], length, self.nb_filter)

    def call(self, x, mask=None):
        x = K.expand_dims(x, 2)  # add a dummy dimension
        output = K.conv2d(x, self.W, strides=self.subsample,
                          border_mode=self.border_mode,
                          dim_ordering='tf')
        output = K.squeeze(output, 2)  # remove the dummy dimension
        if self.bias:
            output += K.reshape(self.b, (1, 1, self.nb_filter))
        output = self.activation(output)
        return output

    def get_config(self):
        config = {'nb_filter': self.nb_filter,
                  'filter_length': self.filter_length,
                  'init': self.init.__name__,
                  'activation': self.activation.__name__,
                  'border_mode': self.border_mode,
                  'subsample_length': self.subsample_length,
                  'W_regularizer': self.W_regularizer.get_config() if self.W_regularizer else None,
                  'b_regularizer': self.b_regularizer.get_config() if self.b_regularizer else None,
                  'activity_regularizer': self.activity_regularizer.get_config() if self.activity_regularizer else None,
                  'W_constraint': self.W_constraint.get_config() if self.W_constraint else None,
                  'b_constraint': self.b_constraint.get_config() if self.b_constraint else None,
                  'bias': self.bias,
                  'input_dim': self.input_dim,
                  'input_length': self.input_length}
        base_config = super(Convolution1D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class AtrousConvolution1D(Convolution1D):
    '''Atrous Convolution operator for filtering neighborhoods of one-dimensional inputs.
    A.k.a dilated convolution or convolution with holes.
    When using this layer as the first layer in a model,
    either provide the keyword argument `input_dim`
    (int, e.g. 128 for sequences of 128-dimensional vectors),
    or `input_shape` (tuples of integers, e.g. (10, 128) for sequences
    of 10 vectors of 128-dimensional vectors).

    # Example

    ```python
        # apply an atrous convolution 1d with atrous rate 2 of length 3 to a sequence with 10 timesteps,
        # with 64 output filters
        model = Sequential()
        model.add(AtrousConvolution1D(64, 3, atrous_rate=2, border_mode='same', input_shape=(10, 32)))
        # now model.output_shape == (None, 10, 64)

        # add a new atrous conv1d on top
        model.add(AtrousConvolution1D(32, 3, atrous_rate=2, border_mode='same'))
        # now model.output_shape == (None, 10, 32)
    ```

    # Arguments
        nb_filter: Number of convolution kernels to use
            (dimensionality of the output).
        filter_length: The extension (spatial or temporal) of each filter.
        init: name of initialization function for the weights of the layer
            (see [initializations](../initializations.md)),
            or alternatively, Theano function to use for weights initialization.
            This parameter is only relevant if you don't pass a `weights` argument.
        activation: name of activation function to use
            (see [activations](../activations.md)),
            or alternatively, elementwise Theano function.
            If you don't specify anything, no activation is applied
            (ie. "linear" activation: a(x) = x).
        weights: list of numpy arrays to set as initial weights.
        border_mode: 'valid', 'same' or 'full'. ('full' requires the Theano backend.)
        subsample_length: factor by which to subsample output.
        atrous_rate: Factor for kernel dilation. Also called filter_dilation
            elsewhere.
        W_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the main weights matrix.
        b_regularizer: instance of [WeightRegularizer](../regularizers.md),
            applied to the bias.
        activity_regularizer: instance of [ActivityRegularizer](../regularizers.md),
            applied to the network output.
        W_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the main weights matrix.
        b_constraint: instance of the [constraints](../constraints.md) module,
            applied to the bias.
        bias: whether to include a bias
            (i.e. make the layer affine rather than linear).
        input_dim: Number of channels/dimensions in the input.
            Either this argument or the keyword argument `input_shape`must be
            provided when using this layer as the first layer in a model.
        input_length: Length of input sequences, when it is constant.
            This argument is required if you are going to connect
            `Flatten` then `Dense` layers upstream
            (without it, the shape of the dense outputs cannot be computed).

    # Input shape
        3D tensor with shape: `(samples, steps, input_dim)`.

    # Output shape
        3D tensor with shape: `(samples, new_steps, nb_filter)`.
        `steps` value might have changed due to padding.
    '''
    def __init__(self, nb_filter, filter_length,
                 init='glorot_uniform', activation=None, weights=None,
                 border_mode='valid', subsample_length=1, atrous_rate=1,
                 W_regularizer=None, b_regularizer=None, activity_regularizer=None,
                 W_constraint=None, b_constraint=None,
                 bias=True, **kwargs):

        if border_mode not in {'valid', 'same', 'full'}:
            raise ValueError('Invalid border mode for AtrousConv1D:', border_mode)

        self.atrous_rate = int(atrous_rate)

        super(AtrousConvolution1D, self).__init__(nb_filter, filter_length,
                                                  init=init, activation=activation,
                                                  weights=weights, border_mode=border_mode,
                                                  subsample_length=subsample_length,
                                                  W_regularizer=W_regularizer, b_regularizer=b_regularizer,
                                                  activity_regularizer=activity_regularizer,
                                                  W_constraint=W_constraint, b_constraint=b_constraint,
                                                  bias=bias, **kwargs)

    def get_output_shape_for(self, input_shape):
        length = conv_output_length(input_shape[1],
                                    self.filter_length,
                                    self.border_mode,
                                    self.subsample[0],
                                    dilation=self.atrous_rate)
        return (input_shape[0], length, self.nb_filter)

    def call(self, x, mask=None):
        x = K.expand_dims(x, 2)  # add a dummy dimension
        output = K.conv2d(x, self.W, strides=self.subsample,
                          border_mode=self.border_mode,
                          dim_ordering='tf',
                          filter_dilation=(self.atrous_rate, self.atrous_rate))
        output = K.squeeze(output, 2)  # remove the dummy dimension
        if self.bias:
            output += K.reshape(self.b, (1, 1, self.nb_filter))
        output = self.activation(output)
        return output

    def get_config(self):
        config = {'atrous_rate': self.atrous_rate}
        base_config = super(AtrousConvolution1D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class Convolution2D(Layer):
    '''Convolution operator for filtering windows of two-dimensional inputs.
    When using this layer as the first layer in a model,
    provide the keyword argument `input_shape`
    (tuple of integers, does not include the sample axis),
    e.g. `input_shape=(3, 128, 128)` for 128x128 RGB pictures.
    # Examples

    ```python
        # apply a 3x3 convolution with 64 output filters on a 256x256 image:
        model = Sequential()
        model.add(Convolution2D(64, 3, 3, border_mode='same', input_shape=(3, 256, 256)))
        # now model.output_shape == (None, 64, 256, 256)

        # add a 3x3 convolution on top, with 32 output filters:
        model.add(Convolution2D(32, 3, 3, border_mode='same'))
        # now model.output_shape == (None, 32, 256, 256)
    ```

    # Arguments
        nb_filter: Number of convolution filters to use.
        nb_row: Number of rows in the convolution kernel.
        nb_col: Number of columns in the convolution kernel.
        init: name of initialization function for the weights of the layer
            (see [initializations](../initializations.md)), or alternatively,
            Theano function to use for weights initialization.
            This parameter is only relevant if you don't pass
            a `weights` argument.
        activation: name of activation function to use
            (see [activations](../activations.md)),
            or alternatively, elementwise Theano function.
            If you don't specify anything, no activation is applied
            (ie. "linear" activation: a(x) = x).
        weights: list of numpy arrays to set as initial weights.
        border_mode: 'valid', 'same' or 'full'. ('full' requires the Theano backend.)
        subsample: tuple of length 2. Factor by which to subsample output.
            Also called strides elsewhere.
        W_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the main weights matrix.
        b_regularizer: instance of [WeightRegularizer](../regularizers.md),
            applied to the bias.
        activity_regularizer: instance of [ActivityRegularizer](../regularizers.md),
            applied to the network output.
        W_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the main weights matrix.
        b_constraint: instance of the [constraints](../constraints.md) module,
            applied to the bias.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".
        bias: whether to include a bias
            (i.e. make the layer affine rather than linear).

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(samples, nb_filter, new_rows, new_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, new_rows, new_cols, nb_filter)` if dim_ordering='tf'.
        `rows` and `cols` values might have changed due to padding.
    '''
    def __init__(self, nb_filter, nb_row, nb_col,
                 init='glorot_uniform', activation='linear', weights=None,
                 border_mode='valid', subsample=(1, 1),
                 atrous_rate=(1, 1), dim_ordering='default',
                 W_regularizer=None, b_regularizer=None, activity_regularizer=None,
                 W_constraint=None, b_constraint=None,
                 bias=True, **kwargs):
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()
        if border_mode not in {'valid', 'same','full'}:
            raise Exception('Invalid border mode for AtrousConv2D:', border_mode)
        self.atrous_rate = tuple(atrous_rate)
        self.nb_filter = nb_filter
        self.nb_row = nb_row
        self.nb_col = nb_col
        self.init = initializations.get(init, dim_ordering=dim_ordering)
        self.activation = activations.get(activation)
        self.border_mode = border_mode
        self.subsample = tuple(subsample)
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering

        self.W_regularizer = regularizers.get(W_regularizer)
        self.b_regularizer = regularizers.get(b_regularizer)
        self.activity_regularizer = regularizers.get(activity_regularizer)

        self.W_constraint = constraints.get(W_constraint)
        self.b_constraint = constraints.get(b_constraint)

        self.bias = bias
        self.input_spec = [InputSpec(ndim=4)]
        self.initial_weights = weights

        #self.dilated = dilated
        #self.rate = rate
        super(Convolution2D, self).__init__(**kwargs)

    def build(self, input_shape):
        if self.dim_ordering == 'th':
            stack_size = input_shape[1]
            self.W_shape = (self.nb_filter, stack_size, self.nb_row, self.nb_col)
        elif self.dim_ordering == 'tf':
            stack_size = input_shape[3]
            self.W_shape = (self.nb_row, self.nb_col, stack_size, self.nb_filter)
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)
        self.W = self.add_weight(self.W_shape,
                                 initializer=self.init,
                                 name='{}_W'.format(self.name),
                                 regularizer=self.W_regularizer,
                                 constraint=self.W_constraint)
        if self.bias:
            self.b = self.add_weight((self.nb_filter,),
                                     initializer='zero',
                                     name='{}_b'.format(self.name),
                                     regularizer=self.b_regularizer,
                                     constraint=self.b_constraint)
        else:
            self.b = None

        if self.initial_weights is not None:
            self.set_weights(self.initial_weights)
            del self.initial_weights
        self.built = True

    def get_output_shape_for(self, input_shape):
        #input_shape = K.shape(self.get_input(train=True))
        if self.dim_ordering == 'th':
            rows = input_shape[2]
            cols = input_shape[3]
        elif self.dim_ordering == 'tf':
            rows = input_shape[1]
            cols = input_shape[2]
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

        rows = conv_output_length(rows, self.nb_row, self.border_mode,
                                  self.subsample[0], dilation=self.atrous_rate[0])
        cols = conv_output_length(cols, self.nb_col, self.border_mode,
                                  self.subsample[1], dilation=self.atrous_rate[1])

        if self.dim_ordering == 'th':
            return (input_shape[0], self.nb_filter, rows, cols)
        elif self.dim_ordering == 'tf':
            return (input_shape[0], rows, cols, self.nb_filter)

    def call(self, x, mask=None):
        output = K.conv2d(x, self.W, strides=self.subsample,
                          border_mode=self.border_mode,
                          dim_ordering=self.dim_ordering,
                          filter_dilation=self.atrous_rate,
                          filter_shape=self.W_shape)
        if self.bias:
            if self.dim_ordering == 'th':
                output += K.reshape(self.b, (1, self.nb_filter, 1, 1))
            elif self.dim_ordering == 'tf':
                output += K.reshape(self.b, (1, 1, 1, self.nb_filter))
            else:
                raise ValueError('Invalid dim_ordering:', self.dim_ordering)
        output = self.activation(output)
        return output

    def get_config(self):
        config = {'nb_filter': self.nb_filter,
                  'nb_row': self.nb_row,
                  'nb_col': self.nb_col,
                  'init': self.init.__name__,
                  'activation': self.activation.__name__,
                  'border_mode': self.border_mode,
                  'subsample': self.subsample,
                  'dim_ordering': self.dim_ordering,
                  'W_regularizer': self.W_regularizer.get_config() if self.W_regularizer else None,
                  'b_regularizer': self.b_regularizer.get_config() if self.b_regularizer else None,
                  'activity_regularizer': self.activity_regularizer.get_config() if self.activity_regularizer else None,
                  'W_constraint': self.W_constraint.get_config() if self.W_constraint else None,
                  'b_constraint': self.b_constraint.get_config() if self.b_constraint else None,
                  'bias': self.bias,
                  'atrous_rate':self.atrous_rate,
                  #'rate':self.rate
                  }
        base_config = super(Convolution2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class Deconvolution2D(Convolution2D):
    '''Transposed convolution operator for filtering windows of two-dimensional inputs.
    The need for transposed convolutions generally arises from the desire
    to use a transformation going in the opposite direction of a normal convolution,
    i.e., from something that has the shape of the output of some convolution
    to something that has the shape of its input
    while maintaining a connectivity pattern that is compatible with said convolution. [1]

    When using this layer as the first layer in a model,
    provide the keyword argument `input_shape`
    (tuple of integers, does not include the sample axis),
    e.g. `input_shape=(3, 128, 128)` for 128x128 RGB pictures.

    To pass the correct `output_shape` to this layer,
    one could use a test model to predict and observe the actual output shape.

    # Examples

    ```python
        # apply a 3x3 transposed convolution with stride 1x1 and 3 output filters on a 12x12 image:
        model = Sequential()
        model.add(Deconvolution2D(3, 3, 3, output_shape=(None, 3, 14, 14), border_mode='valid', input_shape=(3, 12, 12)))
        # Note that you will have to change the output_shape depending on the backend used.

        # we can predict with the model and print the shape of the array.
        dummy_input = np.ones((32, 3, 12, 12))
        # For TensorFlow dummy_input = np.ones((32, 12, 12, 3))
        preds = model.predict(dummy_input)
        print(preds.shape)
        # Theano GPU: (None, 3, 13, 13)
        # Theano CPU: (None, 3, 14, 14)
        # TensorFlow: (None, 14, 14, 3)

        # apply a 3x3 transposed convolution with stride 2x2 and 3 output filters on a 12x12 image:
        model = Sequential()
        model.add(Deconvolution2D(3, 3, 3, output_shape=(None, 3, 25, 25), subsample=(2, 2), border_mode='valid', input_shape=(3, 12, 12)))
        model.summary()

        # we can predict with the model and print the shape of the array.
        dummy_input = np.ones((32, 3, 12, 12))
        # For TensorFlow dummy_input = np.ones((32, 12, 12, 3))
        preds = model.predict(dummy_input)
        print(preds.shape)
        # Theano GPU: (None, 3, 25, 25)
        # Theano CPU: (None, 3, 25, 25)
        # TensorFlow: (None, 25, 25, 3)
    ```

    # Arguments
        nb_filter: Number of transposed convolution filters to use.
        nb_row: Number of rows in the transposed convolution kernel.
        nb_col: Number of columns in the transposed convolution kernel.
        output_shape: Output shape of the transposed convolution operation.
            tuple of integers (nb_samples, nb_filter, nb_output_rows, nb_output_cols)
            Formula for calculation of the output shape [1], [2]:
                o = s (i - 1) + a + k - 2p, \quad a \in \{0, \ldots, s - 1\}
                where:
                    i - input size (rows or cols),
                    k - kernel size (nb_filter),
                    s - stride (subsample for rows or cols respectively),
                    p - padding size,
                    a - user-specified quantity used to distinguish between
                        the s different possible output sizes.
             Because a is not specified explicitly and Theano and Tensorflow
             use different values, it is better to use a dummy input and observe
             the actual output shape of a layer as specified in the examples.
        init: name of initialization function for the weights of the layer
            (see [initializations](../initializations.md)), or alternatively,
            Theano function to use for weights initialization.
            This parameter is only relevant if you don't pass
            a `weights` argument.
        activation: name of activation function to use
            (see [activations](../activations.md)),
            or alternatively, elementwise Theano/TensorFlow function.
            If you don't specify anything, no activation is applied
            (ie. "linear" activation: a(x) = x).
        weights: list of numpy arrays to set as initial weights.
        border_mode: 'valid', 'same' or 'full'. ('full' requires the Theano backend.)
        subsample: tuple of length 2. Factor by which to oversample output.
            Also called strides elsewhere.
        W_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the main weights matrix.
        b_regularizer: instance of [WeightRegularizer](../regularizers.md),
            applied to the bias.
        activity_regularizer: instance of [ActivityRegularizer](../regularizers.md),
            applied to the network output.
        W_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the main weights matrix.
        b_constraint: instance of the [constraints](../constraints.md) module,
            applied to the bias.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".
        bias: whether to include a bias (i.e. make the layer affine rather than linear).

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(samples, nb_filter, new_rows, new_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, new_rows, new_cols, nb_filter)` if dim_ordering='tf'.
        `rows` and `cols` values might have changed due to padding.

    # References
        [1] [A guide to convolution arithmetic for deep learning](https://arxiv.org/abs/1603.07285 "arXiv:1603.07285v1 [stat.ML]")
        [2] [Transposed convolution arithmetic](http://deeplearning.net/software/theano_versions/dev/tutorial/conv_arithmetic.html#transposed-convolution-arithmetic)
        [3] [Deconvolutional Networks](http://www.matthewzeiler.com/pubs/cvpr2010/cvpr2010.pdf)
    '''
    def __init__(self, nb_filter, nb_row, nb_col, output_shape,
                 init='glorot_uniform', activation=None, weights=None,
                 border_mode='valid', subsample=(1, 1),
                 dim_ordering='default',
                 W_regularizer=None, b_regularizer=None, activity_regularizer=None,
                 W_constraint=None, b_constraint=None,
                 bias=True, **kwargs):
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()
        if border_mode not in {'valid', 'same', 'full'}:
            raise ValueError('Invalid border mode for Deconvolution2D:', border_mode)

        self.output_shape_ = output_shape

        super(Deconvolution2D, self).__init__(nb_filter, nb_row, nb_col,
                                              init=init,
                                              activation=activation,
                                              weights=weights,
                                              border_mode=border_mode,
                                              subsample=subsample,
                                              dim_ordering=dim_ordering,
                                              W_regularizer=W_regularizer,
                                              b_regularizer=b_regularizer,
                                              activity_regularizer=activity_regularizer,
                                              W_constraint=W_constraint,
                                              b_constraint=b_constraint,
                                              bias=bias,
                                              **kwargs)

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            rows = self.output_shape_[2]
            cols = self.output_shape_[3]
        elif self.dim_ordering == 'tf':
            rows = self.output_shape_[1]
            cols = self.output_shape_[2]
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

        if self.dim_ordering == 'th':
            return (input_shape[0], self.nb_filter, rows, cols)
        elif self.dim_ordering == 'tf':
            return (input_shape[0], rows, cols, self.nb_filter)

    def call(self, x, mask=None):
        output = K.deconv2d(x, self.W, self.output_shape_,
                            strides=self.subsample,
                            border_mode=self.border_mode,
                            dim_ordering=self.dim_ordering,
                            filter_shape=self.W_shape)
        if self.bias:
            if self.dim_ordering == 'th':
                output += K.reshape(self.b, (1, self.nb_filter, 1, 1))
            elif self.dim_ordering == 'tf':
                output += K.reshape(self.b, (1, 1, 1, self.nb_filter))
            else:
                raise ValueError('Invalid dim_ordering:', self.dim_ordering)
        output = self.activation(output)
        return output

    def get_config(self):
        config = {'output_shape': self.output_shape_}
        base_config = super(Deconvolution2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class AtrousConvolution2D(Convolution2D):
    '''Atrous Convolution operator for filtering windows of two-dimensional inputs.
    A.k.a dilated convolution or convolution with holes.
    When using this layer as the first layer in a model,
    provide the keyword argument `input_shape`
    (tuple of integers, does not include the sample axis),
    e.g. `input_shape=(3, 128, 128)` for 128x128 RGB pictures.

    # Examples

    ```python
        # apply a 3x3 convolution with atrous rate 2x2 and 64 output filters on a 256x256 image:
        model = Sequential()
        model.add(AtrousConvolution2D(64, 3, 3, atrous_rate=(2,2), border_mode='valid', input_shape=(3, 256, 256)))
        # now the actual kernel size is dilated from 3x3 to 5x5 (3+(3-1)*(2-1)=5)
        # thus model.output_shape == (None, 64, 252, 252)
    ```

    # Arguments
        nb_filter: Number of convolution filters to use.
        nb_row: Number of rows in the convolution kernel.
        nb_col: Number of columns in the convolution kernel.
        init: name of initialization function for the weights of the layer
            (see [initializations](../initializations.md)), or alternatively,
            Theano function to use for weights initialization.
            This parameter is only relevant if you don't pass
            a `weights` argument.
        activation: name of activation function to use
            (see [activations](../activations.md)),
            or alternatively, elementwise Theano function.
            If you don't specify anything, no activation is applied
            (ie. "linear" activation: a(x) = x).
        weights: list of numpy arrays to set as initial weights.
        border_mode: 'valid', 'same' or 'full'. ('full' requires the Theano backend.)
        subsample: tuple of length 2. Factor by which to subsample output.
            Also called strides elsewhere.
        atrous_rate: tuple of length 2. Factor for kernel dilation.
            Also called filter_dilation elsewhere.
        W_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the main weights matrix.
        b_regularizer: instance of [WeightRegularizer](../regularizers.md),
            applied to the bias.
        activity_regularizer: instance of [ActivityRegularizer](../regularizers.md),
            applied to the network output.
        W_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the main weights matrix.
        b_constraint: instance of the [constraints](../constraints.md) module,
            applied to the bias.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".
        bias: whether to include a bias (i.e. make the layer affine rather than linear).

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(samples, nb_filter, new_rows, new_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, new_rows, new_cols, nb_filter)` if dim_ordering='tf'.
        `rows` and `cols` values might have changed due to padding.

    # References
        - [Multi-Scale Context Aggregation by Dilated Convolutions](https://arxiv.org/abs/1511.07122)
    '''
    def __init__(self, nb_filter, nb_row, nb_col,
                 init='glorot_uniform', activation=None, weights=None,
                 border_mode='valid', subsample=(1, 1),
                 atrous_rate=(1, 1), dim_ordering='default',
                 W_regularizer=None, b_regularizer=None, activity_regularizer=None,
                 W_constraint=None, b_constraint=None,
                 bias=True, **kwargs):
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()

        if border_mode not in {'valid', 'same', 'full'}:
            raise ValueError('Invalid border mode for AtrousConv2D:', border_mode)

        self.atrous_rate = tuple(atrous_rate)

        super(AtrousConvolution2D, self).__init__(nb_filter, nb_row, nb_col,
                                                  init=init,
                                                  activation=activation,
                                                  weights=weights,
                                                  border_mode=border_mode,
                                                  subsample=subsample,
                                                  dim_ordering=dim_ordering,
                                                  W_regularizer=W_regularizer,
                                                  b_regularizer=b_regularizer,
                                                  activity_regularizer=activity_regularizer,
                                                  W_constraint=W_constraint,
                                                  b_constraint=b_constraint,
                                                  bias=bias,
                                                  **kwargs)

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            rows = input_shape[2]
            cols = input_shape[3]
        elif self.dim_ordering == 'tf':
            rows = input_shape[1]
            cols = input_shape[2]
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

        rows = conv_output_length(rows, self.nb_row, self.border_mode,
                                  self.subsample[0],
                                  dilation=self.atrous_rate[0])
        cols = conv_output_length(cols, self.nb_col, self.border_mode,
                                  self.subsample[1],
                                  dilation=self.atrous_rate[1])

        if self.dim_ordering == 'th':
            return (input_shape[0], self.nb_filter, rows, cols)
        elif self.dim_ordering == 'tf':
            return (input_shape[0], rows, cols, self.nb_filter)

    def call(self, x, mask=None):
        output = K.conv2d(x, self.W, strides=self.subsample,
                          border_mode=self.border_mode,
                          dim_ordering=self.dim_ordering,
                          filter_shape=self.W_shape,
                          filter_dilation=self.atrous_rate)
        if self.bias:
            if self.dim_ordering == 'th':
                output += K.reshape(self.b, (1, self.nb_filter, 1, 1))
            elif self.dim_ordering == 'tf':
                output += K.reshape(self.b, (1, 1, 1, self.nb_filter))
            else:
                raise ValueError('Invalid dim_ordering:', self.dim_ordering)
        output = self.activation(output)
        return output

    def get_config(self):
        config = {'atrous_rate': self.atrous_rate}
        base_config = super(AtrousConvolution2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class SeparableConvolution2D(Layer):
    '''Separable convolution operator for 2D inputs.

    Separable convolutions consist in first performing
    a depthwise spatial convolution
    (which acts on each input channel separately)
    followed by a pointwise convolution which mixes together the resulting
    output channels. The `depth_multiplier` argument controls how many
    output channels are generated per input channel in the depthwise step.

    Intuitively, separable convolutions can be understood as
    a way to factorize a convolution kernel into two smaller kernels,
    or as an extreme version of an Inception block.

    When using this layer as the first layer in a model,
    provide the keyword argument `input_shape`
    (tuple of integers, does not include the sample axis),
    e.g. `input_shape=(3, 128, 128)` for 128x128 RGB pictures.

    # Theano warning

    This layer is only available with the
    TensorFlow backend for the time being.

    # Arguments
        nb_filter: Number of convolution filters to use.
        nb_row: Number of rows in the convolution kernel.
        nb_col: Number of columns in the convolution kernel.
        init: name of initialization function for the weights of the layer
            (see [initializations](../initializations.md)), or alternatively,
            Theano function to use for weights initialization.
            This parameter is only relevant if you don't pass
            a `weights` argument.
        activation: name of activation function to use
            (see [activations](../activations.md)),
            or alternatively, elementwise Theano function.
            If you don't specify anything, no activation is applied
            (ie. "linear" activation: a(x) = x).
        weights: list of numpy arrays to set as initial weights.
        border_mode: 'valid' or 'same'.
        subsample: tuple of length 2. Factor by which to subsample output.
            Also called strides elsewhere.
        depth_multiplier: how many output channel to use per input channel
            for the depthwise convolution step.
        depthwise_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the depthwise weights matrix.
        pointwise_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the pointwise weights matrix.
        b_regularizer: instance of [WeightRegularizer](../regularizers.md),
            applied to the bias.
        activity_regularizer: instance of [ActivityRegularizer](../regularizers.md),
            applied to the network output.
        depthwise_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the depthwise weights matrix.
        pointwise_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the pointwise weights matrix.
        b_constraint: instance of the [constraints](../constraints.md) module,
            applied to the bias.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".
        bias: whether to include a bias
            (i.e. make the layer affine rather than linear).

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(samples, nb_filter, new_rows, new_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, new_rows, new_cols, nb_filter)` if dim_ordering='tf'.
        `rows` and `cols` values might have changed due to padding.
    '''
    def __init__(self, nb_filter, nb_row, nb_col,
                 init='glorot_uniform', activation=None, weights=None,
                 border_mode='valid', subsample=(1, 1),
                 depth_multiplier=1, dim_ordering='default',
                 depthwise_regularizer=None, pointwise_regularizer=None,
                 b_regularizer=None, activity_regularizer=None,
                 depthwise_constraint=None, pointwise_constraint=None,
                 b_constraint=None,
                 bias=True, **kwargs):

        if K.backend() != 'tensorflow':
            raise RuntimeError('SeparableConv2D is only available '
                               'with TensorFlow for the time being.')

        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()

        if border_mode not in {'valid', 'same'}:
            raise ValueError('Invalid border mode for SeparableConv2D:', border_mode)

        if border_mode not in {'valid', 'same'}:
            raise ValueError('Invalid border mode for SeparableConv2D:', border_mode)
        self.nb_filter = nb_filter
        self.nb_row = nb_row
        self.nb_col = nb_col
        self.init = initializations.get(init, dim_ordering=dim_ordering)
        self.activation = activations.get(activation)
        if border_mode not in {'valid', 'same'}:
            raise ValueError('border_mode must be in {valid, same}.')
        self.border_mode = border_mode
        self.subsample = tuple(subsample)
        self.depth_multiplier = depth_multiplier
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering

        self.depthwise_regularizer = regularizers.get(depthwise_regularizer)
        self.pointwise_regularizer = regularizers.get(pointwise_regularizer)
        self.b_regularizer = regularizers.get(b_regularizer)
        self.activity_regularizer = regularizers.get(activity_regularizer)

        self.depthwise_constraint = constraints.get(depthwise_constraint)
        self.pointwise_constraint = constraints.get(pointwise_constraint)
        self.b_constraint = constraints.get(b_constraint)

        self.bias = bias
        self.input_spec = [InputSpec(ndim=4)]
        self.initial_weights = weights
        super(SeparableConvolution2D, self).__init__(**kwargs)

    def build(self, input_shape):
        if self.dim_ordering == 'th':
            stack_size = input_shape[1]
            depthwise_shape = (self.depth_multiplier, stack_size, self.nb_row, self.nb_col)
            pointwise_shape = (self.nb_filter, self.depth_multiplier * stack_size, 1, 1)
        elif self.dim_ordering == 'tf':
            stack_size = input_shape[3]
            depthwise_shape = (self.nb_row, self.nb_col, stack_size, self.depth_multiplier)
            pointwise_shape = (1, 1, self.depth_multiplier * stack_size, self.nb_filter)
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

        self.depthwise_kernel = self.add_weight(depthwise_shape,
                                                initializer=self.init,
                                                regularizer=self.depthwise_regularizer,
                                                constraint=self.depthwise_constraint,
                                                name='{}_depthwise_kernel'.format(self.name))
        self.pointwise_kernel = self.add_weight(pointwise_shape,
                                                initializer=self.init,
                                                regularizer=self.pointwise_regularizer,
                                                constraint=self.pointwise_constraint,
                                                name='{}_pointwise_kernel'.format(self.name))
        if self.bias:
            self.b = self.add_weight((self.nb_filter,),
                                     initializer='zero',
                                     name='{}_b'.format(self.name),
                                     regularizer=self.b_regularizer,
                                     constraint=self.b_constraint)
        else:
            self.b = None

        if self.initial_weights is not None:
            self.set_weights(self.initial_weights)
            del self.initial_weights
        self.built = True

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            rows = input_shape[2]
            cols = input_shape[3]
        elif self.dim_ordering == 'tf':
            rows = input_shape[1]
            cols = input_shape[2]
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

        rows = conv_output_length(rows, self.nb_row,
                                  self.border_mode, self.subsample[0])
        cols = conv_output_length(cols, self.nb_col,
                                  self.border_mode, self.subsample[1])

        if self.dim_ordering == 'th':
            return (input_shape[0], self.nb_filter, rows, cols)
        elif self.dim_ordering == 'tf':
            return (input_shape[0], rows, cols, self.nb_filter)
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        output = K.separable_conv2d(x, self.depthwise_kernel,
                                    self.pointwise_kernel,
                                    strides=self.subsample,
                                    border_mode=self.border_mode,
                                    dim_ordering=self.dim_ordering)
        if self.bias:
            if self.dim_ordering == 'th':
                output += K.reshape(self.b, (1, self.nb_filter, 1, 1))
            elif self.dim_ordering == 'tf':
                output += K.reshape(self.b, (1, 1, 1, self.nb_filter))
            else:
                raise ValueError('Invalid dim_ordering:', self.dim_ordering)
        output = self.activation(output)
        return output

    def get_config(self):
        config = {'nb_filter': self.nb_filter,
                  'nb_row': self.nb_row,
                  'nb_col': self.nb_col,
                  'init': self.init.__name__,
                  'activation': self.activation.__name__,
                  'border_mode': self.border_mode,
                  'subsample': self.subsample,
                  'depth_multiplier': self.depth_multiplier,
                  'dim_ordering': self.dim_ordering,
                  'depthwise_regularizer': self.depthwise_regularizer.get_config() if self.depthwise_regularizer else None,
                  'pointwise_regularizer': self.depthwise_regularizer.get_config() if self.depthwise_regularizer else None,
                  'b_regularizer': self.b_regularizer.get_config() if self.b_regularizer else None,
                  'activity_regularizer': self.activity_regularizer.get_config() if self.activity_regularizer else None,
                  'depthwise_constraint': self.depthwise_constraint.get_config() if self.depthwise_constraint else None,
                  'pointwise_constraint': self.pointwise_constraint.get_config() if self.pointwise_constraint else None,
                  'b_constraint': self.b_constraint.get_config() if self.b_constraint else None,
                  'bias': self.bias}
        base_config = super(SeparableConvolution2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class Convolution3D(Layer):
    '''Convolution operator for filtering windows of three-dimensional inputs.
    When using this layer as the first layer in a model,
    provide the keyword argument `input_shape`
    (tuple of integers, does not include the sample axis),
    e.g. `input_shape=(3, 10, 128, 128)` for 10 frames of 128x128 RGB pictures.

    # Arguments
        nb_filter: Number of convolution filters to use.
        kernel_dim1: Length of the first dimension in the convolution kernel.
        kernel_dim2: Length of the second dimension in the convolution kernel.
        kernel_dim3: Length of the third dimension in the convolution kernel.
        init: name of initialization function for the weights of the layer
            (see [initializations](../initializations.md)), or alternatively,
            Theano function to use for weights initialization.
            This parameter is only relevant if you don't pass
            a `weights` argument.
        activation: name of activation function to use
            (see [activations](../activations.md)),
            or alternatively, elementwise Theano function.
            If you don't specify anything, no activation is applied
            (ie. "linear" activation: a(x) = x).
        weights: list of Numpy arrays to set as initial weights.
        border_mode: 'valid', 'same' or 'full'. ('full' requires the Theano backend.)
        subsample: tuple of length 3. Factor by which to subsample output.
            Also called strides elsewhere.
            Note: 'subsample' is implemented by slicing the output of conv3d with strides=(1,1,1).
        W_regularizer: instance of [WeightRegularizer](../regularizers.md)
            (eg. L1 or L2 regularization), applied to the main weights matrix.
        b_regularizer: instance of [WeightRegularizer](../regularizers.md),
            applied to the bias.
        activity_regularizer: instance of [ActivityRegularizer](../regularizers.md),
            applied to the network output.
        W_constraint: instance of the [constraints](../constraints.md) module
            (eg. maxnorm, nonneg), applied to the main weights matrix.
        b_constraint: instance of the [constraints](../constraints.md) module,
            applied to the bias.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 4.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".
        bias: whether to include a bias (i.e. make the layer affine rather than linear).

    # Input shape
        5D tensor with shape:
        `(samples, channels, conv_dim1, conv_dim2, conv_dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, conv_dim1, conv_dim2, conv_dim3, channels)` if dim_ordering='tf'.

    # Output shape
        5D tensor with shape:
        `(samples, nb_filter, new_conv_dim1, new_conv_dim2, new_conv_dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, new_conv_dim1, new_conv_dim2, new_conv_dim3, nb_filter)` if dim_ordering='tf'.
        `new_conv_dim1`, `new_conv_dim2` and `new_conv_dim3` values might have changed due to padding.
    '''

    def __init__(self, nb_filter, kernel_dim1, kernel_dim2, kernel_dim3,
                 init='glorot_uniform', activation=None, weights=None,
                 border_mode='valid', subsample=(1, 1, 1), dim_ordering='default',
                 W_regularizer=None, b_regularizer=None, activity_regularizer=None,
                 W_constraint=None, b_constraint=None,
                 bias=True, **kwargs):
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()

        if border_mode not in {'valid', 'same', 'full'}:
            raise ValueError('Invalid border mode for Convolution3D:', border_mode)
        self.nb_filter = nb_filter
        self.kernel_dim1 = kernel_dim1
        self.kernel_dim2 = kernel_dim2
        self.kernel_dim3 = kernel_dim3
        self.init = initializations.get(init, dim_ordering=dim_ordering)
        self.activation = activations.get(activation)
        self.border_mode = border_mode
        self.subsample = tuple(subsample)
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering

        self.W_regularizer = regularizers.get(W_regularizer)
        self.b_regularizer = regularizers.get(b_regularizer)
        self.activity_regularizer = regularizers.get(activity_regularizer)

        self.W_constraint = constraints.get(W_constraint)
        self.b_constraint = constraints.get(b_constraint)

        self.bias = bias
        self.input_spec = [InputSpec(ndim=5)]
        self.initial_weights = weights
        super(Convolution3D, self).__init__(**kwargs)

    def build(self, input_shape):
        assert len(input_shape) == 5
        self.input_spec = [InputSpec(shape=input_shape)]

        if self.dim_ordering == 'th':
            stack_size = input_shape[1]
            self.W_shape = (self.nb_filter, stack_size,
                            self.kernel_dim1, self.kernel_dim2, self.kernel_dim3)
        elif self.dim_ordering == 'tf':
            stack_size = input_shape[4]
            self.W_shape = (self.kernel_dim1, self.kernel_dim2, self.kernel_dim3,
                            stack_size, self.nb_filter)
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

        self.W = self.add_weight(self.W_shape,
                                 initializer=self.init,
                                 name='{}_W'.format(self.name),
                                 regularizer=self.W_regularizer,
                                 constraint=self.W_constraint)
        if self.bias:
            self.b = self.add_weight((self.nb_filter,),
                                     initializer='zero',
                                     name='{}_b'.format(self.name),
                                     regularizer=self.b_regularizer,
                                     constraint=self.b_constraint)
        else:
            self.b = None

        if self.initial_weights is not None:
            self.set_weights(self.initial_weights)
            del self.initial_weights
        self.built = True

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            conv_dim1 = input_shape[2]
            conv_dim2 = input_shape[3]
            conv_dim3 = input_shape[4]
        elif self.dim_ordering == 'tf':
            conv_dim1 = input_shape[1]
            conv_dim2 = input_shape[2]
            conv_dim3 = input_shape[3]
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

        conv_dim1 = conv_output_length(conv_dim1, self.kernel_dim1,
                                       self.border_mode, self.subsample[0])
        conv_dim2 = conv_output_length(conv_dim2, self.kernel_dim2,
                                       self.border_mode, self.subsample[1])
        conv_dim3 = conv_output_length(conv_dim3, self.kernel_dim3,
                                       self.border_mode, self.subsample[2])

        if self.dim_ordering == 'th':
            return (input_shape[0], self.nb_filter, conv_dim1, conv_dim2, conv_dim3)
        elif self.dim_ordering == 'tf':
            return (input_shape[0], conv_dim1, conv_dim2, conv_dim3, self.nb_filter)
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        input_shape = self.input_spec[0].shape
        output = K.conv3d(x, self.W, strides=self.subsample,
                          border_mode=self.border_mode,
                          dim_ordering=self.dim_ordering,
                          volume_shape=input_shape,
                          filter_shape=self.W_shape)
        if self.bias:
            if self.dim_ordering == 'th':
                output += K.reshape(self.b, (1, self.nb_filter, 1, 1, 1))
            elif self.dim_ordering == 'tf':
                output += K.reshape(self.b, (1, 1, 1, 1, self.nb_filter))
            else:
                raise ValueError('Invalid dim_ordering:', self.dim_ordering)
        output = self.activation(output)
        return output

    def get_config(self):
        config = {'nb_filter': self.nb_filter,
                  'kernel_dim1': self.kernel_dim1,
                  'kernel_dim2': self.kernel_dim2,
                  'kernel_dim3': self.kernel_dim3,
                  'dim_ordering': self.dim_ordering,
                  'init': self.init.__name__,
                  'activation': self.activation.__name__,
                  'border_mode': self.border_mode,
                  'subsample': self.subsample,
                  'W_regularizer': self.W_regularizer.get_config() if self.W_regularizer else None,
                  'b_regularizer': self.b_regularizer.get_config() if self.b_regularizer else None,
                  'activity_regularizer': self.activity_regularizer.get_config() if self.activity_regularizer else None,
                  'W_constraint': self.W_constraint.get_config() if self.W_constraint else None,
                  'b_constraint': self.b_constraint.get_config() if self.b_constraint else None,
                  'bias': self.bias}
        base_config = super(Convolution3D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))

class _Pooling1D(Layer):
    '''Abstract class for different pooling 1D layers.
    '''
    input_dim = 3

    def __init__(self, pool_length=2, stride=None,
                 border_mode='valid', **kwargs):
        super(_Pooling1D, self).__init__(**kwargs)
        if stride is None:
            stride = pool_length
        self.pool_length = pool_length
        self.stride = stride
        self.st = (self.stride, 1)
        self.pool_size = (pool_length, 1)
        assert border_mode in {'valid', 'same'}, 'border_mode must be in {valid, same}'
        self.border_mode = border_mode
        self.input_spec = [InputSpec(ndim=3)]

    def get_output_shape_for(self, input_shape):
        length = conv_output_length(input_shape[1], self.pool_length,
                                    self.border_mode, self.stride)
        return (input_shape[0], length, input_shape[2])

    def _pooling_function(self, back_end, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        raise NotImplementedError

    def call(self, x, mask=None):
        x = K.expand_dims(x, -1)   # add dummy last dimension
        x = K.permute_dimensions(x, (0, 2, 1, 3))
        output = self._pooling_function(inputs=x, pool_size=self.pool_size,
                                        strides=self.st,
                                        border_mode=self.border_mode,
                                        dim_ordering='th')
        output = K.permute_dimensions(output, (0, 2, 1, 3))
        return K.squeeze(output, 3)  # remove dummy last dimension

    def get_config(self):
        config = {'stride': self.stride,
                  'pool_length': self.pool_length,
                  'border_mode': self.border_mode}
        base_config = super(_Pooling1D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class MaxPooling1D(_Pooling1D):
    '''Max pooling operation for temporal data.

    # Input shape
        3D tensor with shape: `(samples, steps, features)`.

    # Output shape
        3D tensor with shape: `(samples, downsampled_steps, features)`.

    # Arguments
        pool_length: factor by which to downscale. 2 will halve the input.
        stride: integer or None. Stride value.
        border_mode: 'valid' or 'same'.
            Note: 'same' will only work with TensorFlow for the time being.
    '''

    def __init__(self, pool_length=2, stride=None,
                 border_mode='valid', **kwargs):
        super(MaxPooling1D, self).__init__(pool_length, stride,
                                           border_mode, **kwargs)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        output = K.pool2d(inputs, pool_size, strides,
                          border_mode, dim_ordering, pool_mode='max')
        return output


class AveragePooling1D(_Pooling1D):
    '''Average pooling for temporal data.

    # Arguments
        pool_length: factor by which to downscale. 2 will halve the input.
        stride: integer or None. Stride value.
        border_mode: 'valid' or 'same'.
            Note: 'same' will only work with TensorFlow for the time being.

    # Input shape
        3D tensor with shape: `(samples, steps, features)`.

    # Output shape
        3D tensor with shape: `(samples, downsampled_steps, features)`.
    '''

    def __init__(self, pool_length=2, stride=None,
                 border_mode='valid', **kwargs):
        super(AveragePooling1D, self).__init__(pool_length, stride,
                                               border_mode, **kwargs)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        output = K.pool2d(inputs, pool_size, strides,
                          border_mode, dim_ordering, pool_mode='avg')
        return output


class _Pooling2D(Layer):
    '''Abstract class for different pooling 2D layers.
    '''

    def __init__(self, pool_size=(2, 2), strides=None, border_mode='valid',
                 dim_ordering=K.image_dim_ordering(), **kwargs):
        super(_Pooling2D, self).__init__(**kwargs)
        self.pool_size = tuple(pool_size)
        if strides is None:
            strides = self.pool_size
        self.strides = tuple(strides)
        assert border_mode in {'valid', 'same'}, 'border_mode must be in {valid, same}'
        self.border_mode = border_mode
        assert dim_ordering in {'tf', 'th'}, 'dim_ordering must be in {tf, th}'
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=4)]

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            rows = input_shape[2]
            cols = input_shape[3]
        elif self.dim_ordering == 'tf':
            rows = input_shape[1]
            cols = input_shape[2]
        else:
            raise Exception('Invalid dim_ordering: ' + self.dim_ordering)

        rows = conv_output_length(rows, self.pool_size[0],
                                  self.border_mode, self.strides[0])
        cols = conv_output_length(cols, self.pool_size[1],
                                  self.border_mode, self.strides[1])

        if self.dim_ordering == 'th':
            return (input_shape[0], input_shape[1], rows, cols)
        elif self.dim_ordering == 'tf':
            return (input_shape[0], rows, cols, input_shape[3])
        else:
            raise Exception('Invalid dim_ordering: ' + self.dim_ordering)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        raise NotImplementedError

    def call(self, x, mask=None):
        output = self._pooling_function(inputs=x, pool_size=self.pool_size,
                                        strides=self.strides,
                                        border_mode=self.border_mode,
                                        dim_ordering=self.dim_ordering)
        return output

    def get_config(self):
        config = {'pool_size': self.pool_size,
                  'border_mode': self.border_mode,
                  'strides': self.strides,
                  'dim_ordering': self.dim_ordering}
        base_config = super(_Pooling2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class MaxPooling2D(_Pooling2D):
    '''Max pooling operation for spatial data.

    # Arguments
        pool_size: tuple of 2 integers,
            factors by which to downscale (vertical, horizontal).
            (2, 2) will halve the image in each dimension.
        strides: tuple of 2 integers, or None. Strides values.
        border_mode: 'valid' or 'same'.
            Note: 'same' will only work with TensorFlow for the time being.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "th".

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(nb_samples, channels, pooled_rows, pooled_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, pooled_rows, pooled_cols, channels)` if dim_ordering='tf'.
    '''

    def __init__(self, pool_size=(2, 2), strides=None, border_mode='valid',
                 dim_ordering=K.image_dim_ordering(), **kwargs):
        super(MaxPooling2D, self).__init__(pool_size, strides, border_mode,
                                           dim_ordering, **kwargs)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        output = K.pool2d(inputs, pool_size, strides,
                          border_mode, dim_ordering, pool_mode='max')
        return output


class AveragePooling2D(_Pooling2D):
    '''Average pooling operation for spatial data.

    # Arguments
        pool_size: tuple of 2 integers,
            factors by which to downscale (vertical, horizontal).
            (2, 2) will halve the image in each dimension.
        strides: tuple of 2 integers, or None. Strides values.
        border_mode: 'valid' or 'same'.
            Note: 'same' will only work with TensorFlow for the time being.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "th".

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(nb_samples, channels, pooled_rows, pooled_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, pooled_rows, pooled_cols, channels)` if dim_ordering='tf'.
    '''

    def __init__(self, pool_size=(2, 2), strides=None, border_mode='valid',
                 dim_ordering=K.image_dim_ordering(), **kwargs):
        super(AveragePooling2D, self).__init__(pool_size, strides, border_mode,
                                               dim_ordering, **kwargs)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        output = K.pool2d(inputs, pool_size, strides,
                          border_mode, dim_ordering, pool_mode='avg')
        return output


class _Pooling3D(Layer):
    '''Abstract class for different pooling 3D layers.
    '''

    def __init__(self, pool_size=(2, 2, 2), strides=None, border_mode='valid',
                 dim_ordering=K.image_dim_ordering(), **kwargs):
        super(_Pooling3D, self).__init__(**kwargs)
        self.pool_size = tuple(pool_size)
        if strides is None:
            strides = self.pool_size
        self.strides = tuple(strides)
        assert border_mode in {'valid', 'same'}, 'border_mode must be in {valid, same}'
        self.border_mode = border_mode
        assert dim_ordering in {'tf', 'th'}, 'dim_ordering must be in {tf, th}'
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=5)]

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            len_dim1 = input_shape[2]
            len_dim2 = input_shape[3]
            len_dim3 = input_shape[4]
        elif self.dim_ordering == 'tf':
            len_dim1 = input_shape[1]
            len_dim2 = input_shape[2]
            len_dim3 = input_shape[3]
        else:
            raise Exception('Invalid dim_ordering: ' + self.dim_ordering)

        len_dim1 = conv_output_length(len_dim1, self.pool_size[0],
                                      self.border_mode, self.strides[0])
        len_dim2 = conv_output_length(len_dim2, self.pool_size[1],
                                      self.border_mode, self.strides[1])
        len_dim3 = conv_output_length(len_dim3, self.pool_size[2],
                                      self.border_mode, self.strides[2])

        if self.dim_ordering == 'th':
            return (input_shape[0], input_shape[1], len_dim1, len_dim2, len_dim3)
        elif self.dim_ordering == 'tf':
            return (input_shape[0], len_dim1, len_dim2, len_dim3, input_shape[4])
        else:
            raise Exception('Invalid dim_ordering: ' + self.dim_ordering)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        raise NotImplementedError

    def call(self, x, mask=None):
        output = self._pooling_function(inputs=x, pool_size=self.pool_size,
                                        strides=self.strides,
                                        border_mode=self.border_mode,
                                        dim_ordering=self.dim_ordering)
        return output

    def get_config(self):
        config = {'pool_size': self.pool_size,
                  'border_mode': self.border_mode,
                  'strides': self.strides,
                  'dim_ordering': self.dim_ordering}
        base_config = super(_Pooling3D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class MaxPooling3D(_Pooling3D):
    '''Max pooling operation for 3D data (spatial or spatio-temporal).

    Note: this layer will only work with Theano for the time being.

    # Arguments
        pool_size: tuple of 3 integers,
            factors by which to downscale (dim1, dim2, dim3).
            (2, 2, 2) will halve the size of the 3D input in each dimension.
        strides: tuple of 3 integers, or None. Strides values.
        border_mode: 'valid' or 'same'.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 4.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "th".

    # Input shape
        5D tensor with shape:
        `(samples, channels, len_pool_dim1, len_pool_dim2, len_pool_dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, len_pool_dim1, len_pool_dim2, len_pool_dim3, channels)` if dim_ordering='tf'.

    # Output shape
        5D tensor with shape:
        `(nb_samples, channels, pooled_dim1, pooled_dim2, pooled_dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, pooled_dim1, pooled_dim2, pooled_dim3, channels)` if dim_ordering='tf'.
    '''

    def __init__(self, pool_size=(2, 2, 2), strides=None, border_mode='valid',
                 dim_ordering=K.image_dim_ordering(), **kwargs):
        if K._BACKEND != 'theano':
            raise Exception(self.__class__.__name__ +
                            ' is currently only working with Theano backend.')
        super(MaxPooling3D, self).__init__(pool_size, strides, border_mode,
                                           dim_ordering, **kwargs)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        output = K.pool3d(inputs, pool_size, strides,
                          border_mode, dim_ordering, pool_mode='max')
        return output


class AveragePooling3D(_Pooling3D):
    '''Average pooling operation for 3D data (spatial or spatio-temporal).

    Note: this layer will only work with Theano for the time being.

    # Arguments
        pool_size: tuple of 3 integers,
            factors by which to downscale (dim1, dim2, dim3).
            (2, 2, 2) will halve the size of the 3D input in each dimension.
        strides: tuple of 3 integers, or None. Strides values.
        border_mode: 'valid' or 'same'.
        dim_ordering: 'th' or 'tf'. In 'th' mode, the channels dimension
            (the depth) is at index 1, in 'tf' mode is it at index 4.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "th".

    # Input shape
        5D tensor with shape:
        `(samples, channels, len_pool_dim1, len_pool_dim2, len_pool_dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, len_pool_dim1, len_pool_dim2, len_pool_dim3, channels)` if dim_ordering='tf'.

    # Output shape
        5D tensor with shape:
        `(nb_samples, channels, pooled_dim1, pooled_dim2, pooled_dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, pooled_dim1, pooled_dim2, pooled_dim3, channels)` if dim_ordering='tf'.
    '''

    def __init__(self, pool_size=(2, 2, 2), strides=None, border_mode='valid',
                 dim_ordering=K.image_dim_ordering(), **kwargs):
        if K._BACKEND != 'theano':
            raise Exception(self.__class__.__name__ +
                            ' is currently only working with Theano backend.')
        super(AveragePooling3D, self).__init__(pool_size, strides, border_mode,
                                               dim_ordering, **kwargs)

    def _pooling_function(self, inputs, pool_size, strides,
                          border_mode, dim_ordering):
        output = K.pool3d(inputs, pool_size, strides,
                          border_mode, dim_ordering, pool_mode='avg')
        return output

class UpSampling1D(Layer):
    '''Repeat each temporal step `length` times along the time axis.

    # Arguments
        length: integer. Upsampling factor.

    # Input shape
        3D tensor with shape: `(samples, steps, features)`.

    # Output shape
        3D tensor with shape: `(samples, upsampled_steps, features)`.
    '''

    def __init__(self, length=2, **kwargs):
        self.length = length
        self.input_spec = [InputSpec(ndim=3)]
        super(UpSampling1D, self).__init__(**kwargs)

    def get_output_shape_for(self, input_shape):
        length = self.length * input_shape[1] if input_shape[1] is not None else None
        return (input_shape[0], length, input_shape[2])

    def call(self, x, mask=None):
        output = K.repeat_elements(x, self.length, axis=1)
        return output

    def get_config(self):
        config = {'length': self.length}
        base_config = super(UpSampling1D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class UpSampling2D(Layer):
    '''Repeat the rows and columns of the data
    by size[0] and size[1] respectively.

    # Arguments
        size: tuple of 2 integers. The upsampling factors for rows and columns.
        dim_ordering: 'th' or 'tf'.
            In 'th' mode, the channels dimension (the depth)
            is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(samples, channels, upsampled_rows, upsampled_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, upsampled_rows, upsampled_cols, channels)` if dim_ordering='tf'.
    '''

    def __init__(self, size=(2, 2), dim_ordering='default', **kwargs):
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()
        self.size = tuple(size)
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=4)]
        super(UpSampling2D, self).__init__(**kwargs)

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            width = self.size[0] * input_shape[2] if input_shape[2] is not None else None
            height = self.size[1] * input_shape[3] if input_shape[3] is not None else None
            return (input_shape[0],
                    input_shape[1],
                    self.size[0] * input_shape[2] if  input_shape[2] else None,
                    self.size[1] * input_shape[3] if  input_shape[3] else None)

        elif self.dim_ordering == 'tf':
            width = self.size[0] * input_shape[1] if input_shape[1] is not None else None
            height = self.size[1] * input_shape[2] if input_shape[2] is not None else None
            return (input_shape[0],
                    self.size[0] * input_shape[1] if  input_shape[1] else None,
                    self.size[1] * input_shape[2] if  input_shape[2] else None,

                    input_shape[3])
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        return K.resize_images(x, self.size[0], self.size[1],
                               self.dim_ordering)

    def get_config(self):
        config = {'size': self.size}
        base_config = super(UpSampling2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class UpSampling3D(Layer):
    '''Repeat the first, second and third dimension of the data
    by size[0], size[1] and size[2] respectively.

    # Arguments
        size: tuple of 3 integers. The upsampling factors for dim1, dim2 and dim3.
        dim_ordering: 'th' or 'tf'.
            In 'th' mode, the channels dimension (the depth)
            is at index 1, in 'tf' mode is it at index 4.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".

    # Input shape
        5D tensor with shape:
        `(samples, channels, dim1, dim2, dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, dim1, dim2, dim3, channels)` if dim_ordering='tf'.

    # Output shape
        5D tensor with shape:
        `(samples, channels, upsampled_dim1, upsampled_dim2, upsampled_dim3)` if dim_ordering='th'
        or 5D tensor with shape:
        `(samples, upsampled_dim1, upsampled_dim2, upsampled_dim3, channels)` if dim_ordering='tf'.
    '''

    def __init__(self, size=(2, 2, 2), dim_ordering='default', **kwargs):
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()
        self.size = tuple(size)
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=5)]
        super(UpSampling3D, self).__init__(**kwargs)

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            dim1 = self.size[0] * input_shape[2] if input_shape[2] is not None else None
            dim2 = self.size[1] * input_shape[3] if input_shape[3] is not None else None
            dim3 = self.size[2] * input_shape[4] if input_shape[4] is not None else None
            return (input_shape[0],
                    input_shape[1],
                    dim1,
                    dim2,
                    dim3)
        elif self.dim_ordering == 'tf':
            dim1 = self.size[0] * input_shape[1] if input_shape[1] is not None else None
            dim2 = self.size[1] * input_shape[2] if input_shape[2] is not None else None
            dim3 = self.size[2] * input_shape[3] if input_shape[3] is not None else None
            return (input_shape[0],
                    dim1,
                    dim2,
                    dim3,
                    input_shape[4])
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        return K.resize_volumes(x, self.size[0], self.size[1], self.size[2],
                                self.dim_ordering)

    def get_config(self):
        config = {'size': self.size}
        base_config = super(UpSampling3D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class ZeroPadding1D(Layer):
    '''Zero-padding layer for 1D input (e.g. temporal sequence).

    # Arguments
        padding: int, or tuple of int (length 2), or dictionary.
            - If int:
            How many zeros to add at the beginning and end of
            the padding dimension (axis 1).
            - If tuple of int (length 2)
            How many zeros to add at the beginning and at the end of
            the padding dimension, in order '(left_pad, right_pad)'.
            - If dictionary: should contain the keys
            {'left_pad', 'right_pad'}.
            If any key is missing, default value of 0 will be used for the missing key.

    # Input shape
        3D tensor with shape (samples, axis_to_pad, features)

    # Output shape
        3D tensor with shape (samples, padded_axis, features)
    '''

    def __init__(self, padding=1, **kwargs):
        super(ZeroPadding1D, self).__init__(**kwargs)
        self.padding = padding

        if isinstance(padding, int):
            self.left_pad = padding
            self.right_pad = padding

        elif isinstance(padding, dict):
            if set(padding.keys()) <= {'left_pad', 'right_pad'}:
                self.left_pad = padding.get('left_pad', 0)
                self.right_pad = padding.get('right_pad', 0)
            else:
                raise ValueError('Unexpected key found in `padding` dictionary. '
                                 'Keys have to be in {"left_pad", "right_pad"}. '
                                 'Found: ' + str(padding.keys()))
        else:
            padding = tuple(padding)
            if len(padding) != 2:
                raise ValueError('`padding` should be int, or dict with keys '
                                 '{"left_pad", "right_pad"}, or tuple of length 2. '
                                 'Found: ' + str(padding))
            self.left_pad = padding[0]
            self.right_pad = padding[1]
        self.input_spec = [InputSpec(ndim=3)]

    def get_output_shape_for(self, input_shape):
        length = input_shape[1] + self.left_pad + self.right_pad if input_shape[1] is not None else None
        return (input_shape[0],
                length,
                input_shape[2])

    def call(self, x, mask=None):
        return K.asymmetric_temporal_padding(x, left_pad=self.left_pad, right_pad=self.right_pad)

    def get_config(self):
        config = {'padding': self.padding}
        base_config = super(ZeroPadding1D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class ZeroPadding2D(Layer):
    '''Zero-padding layer for 2D input (e.g. picture).

    # Arguments
        padding: tuple of int (length 2), or tuple of int (length 4), or dictionary.
            - If tuple of int (length 2):
            How many zeros to add at the beginning and end of
            the 2 padding dimensions (rows and cols).
            - If tuple of int (length 4):
            How many zeros to add at the beginning and at the end of
            the 2 padding dimensions (rows and cols), in the order
            '(top_pad, bottom_pad, left_pad, right_pad)'.
            - If dictionary: should contain the keys
            {'top_pad', 'bottom_pad', 'left_pad', 'right_pad'}.
            If any key is missing, default value of 0 will be used for the missing key.
        dim_ordering: 'th' or 'tf'.
            In 'th' mode, the channels dimension (the depth)
            is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".

    # Input shape
        4D tensor with shape:
        `(samples, channels, rows, cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, rows, cols, channels)` if dim_ordering='tf'.

    # Output shape
        4D tensor with shape:
        `(samples, channels, padded_rows, padded_cols)` if dim_ordering='th'
        or 4D tensor with shape:
        `(samples, padded_rows, padded_cols, channels)` if dim_ordering='tf'.
    '''

    def __init__(self,
                 padding=(1, 1),
                 dim_ordering='default',
                 **kwargs):
        super(ZeroPadding2D, self).__init__(**kwargs)
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()

        self.padding = padding
        if isinstance(padding, dict):
            if set(padding.keys()) <= {'top_pad', 'bottom_pad', 'left_pad', 'right_pad'}:
                self.top_pad = padding.get('top_pad', 0)
                self.bottom_pad = padding.get('bottom_pad', 0)
                self.left_pad = padding.get('left_pad', 0)
                self.right_pad = padding.get('right_pad', 0)
            else:
                raise ValueError('Unexpected key found in `padding` dictionary. '
                                 'Keys have to be in {"top_pad", "bottom_pad", '
                                 '"left_pad", "right_pad"}.'
                                 'Found: ' + str(padding.keys()))
        else:
            padding = tuple(padding)
            if len(padding) == 2:
                self.top_pad = padding[0]
                self.bottom_pad = padding[0]
                self.left_pad = padding[1]
                self.right_pad = padding[1]
            elif len(padding) == 4:
                self.top_pad = padding[0]
                self.bottom_pad = padding[1]
                self.left_pad = padding[2]
                self.right_pad = padding[3]
            else:
                raise TypeError('`padding` should be tuple of int '
                                'of length 2 or 4, or dict. '
                                'Found: ' + str(padding))

        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=4)]

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            rows = input_shape[2] + self.top_pad + self.bottom_pad if input_shape[2] is not None else None
            cols = input_shape[3] + self.left_pad + self.right_pad if input_shape[3] is not None else None
            return (input_shape[0],
                    input_shape[1],
                    rows,
                    cols)
        elif self.dim_ordering == 'tf':
            rows = input_shape[1] + self.top_pad + self.bottom_pad if input_shape[1] is not None else None
            cols = input_shape[2] + self.left_pad + self.right_pad if input_shape[2] is not None else None
            return (input_shape[0],
                    rows,
                    cols,
                    input_shape[3])
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        return K.asymmetric_spatial_2d_padding(x,
                                               top_pad=self.top_pad,
                                               bottom_pad=self.bottom_pad,
                                               left_pad=self.left_pad,
                                               right_pad=self.right_pad,
                                               dim_ordering=self.dim_ordering)

    def get_config(self):
        config = {'padding': self.padding}
        base_config = super(ZeroPadding2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class ZeroPadding3D(Layer):
    '''Zero-padding layer for 3D data (spatial or spatio-temporal).

    # Arguments
        padding: tuple of int (length 3)
            How many zeros to add at the beginning and end of
            the 3 padding dimensions (axis 3, 4 and 5).
            Currently only symmetric padding is supported.
        dim_ordering: 'th' or 'tf'.
            In 'th' mode, the channels dimension (the depth)
            is at index 1, in 'tf' mode is it at index 4.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".

    # Input shape
        5D tensor with shape:
        (samples, depth, first_axis_to_pad, second_axis_to_pad, third_axis_to_pad)

    # Output shape
        5D tensor with shape:
        (samples, depth, first_padded_axis, second_padded_axis, third_axis_to_pad)
    '''

    def __init__(self, padding=(1, 1, 1), dim_ordering='default', **kwargs):
        super(ZeroPadding3D, self).__init__(**kwargs)
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()
        self.padding = tuple(padding)
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=5)]

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            dim1 = input_shape[2] + 2 * self.padding[0] if input_shape[2] is not None else None
            dim2 = input_shape[3] + 2 * self.padding[1] if input_shape[3] is not None else None
            dim3 = input_shape[4] + 2 * self.padding[2] if input_shape[4] is not None else None
            return (input_shape[0],
                    input_shape[1],
                    dim1,
                    dim2,
                    dim3)
        elif self.dim_ordering == 'tf':
            dim1 = input_shape[1] + 2 * self.padding[0] if input_shape[1] is not None else None
            dim2 = input_shape[2] + 2 * self.padding[1] if input_shape[2] is not None else None
            dim3 = input_shape[3] + 2 * self.padding[2] if input_shape[3] is not None else None
            return (input_shape[0],
                    dim1,
                    dim2,
                    dim3,
                    input_shape[4])
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        return K.spatial_3d_padding(x, padding=self.padding,
                                    dim_ordering=self.dim_ordering)

    def get_config(self):
        config = {'padding': self.padding}
        base_config = super(ZeroPadding3D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))
class Resize3D(Layer):
    '''cropping layer for fully convolutional layer for 2D image(e.g. picture).
    # Input shape
        4D tensor with shape:
        (samples, depth, first_axis_to_pad, second_axis_to_pad)
    # Output shape
        4D tensor with shape:
        (samples, depth, first_padded_axis, second_padded_axis)
    # Arguments
        padding: tuple of int (length 2)
            How many zeros to add at the beginning and end of
            the 2 padding dimensions (axis 3 and 4).
    '''
    input_ndim = 5

    def __init__(self, destin_shape = None, dim_ordering='th',  **kwargs):
        super(Resize2D, self).__init__(**kwargs)

        assert dim_ordering in {'tf', 'th'}, 'dim_ordering must be in {tf, th}'
        self.dim_ordering = dim_ordering
        #self.layerbefore = tuple(layerbefore) # -1 means the previous layer
        assert destin_shape is not None, 'Please specify the destination shape'
        self.destin_shape = destin_shape
        self.input_spec = [InputSpec(ndim=input_ndim)]


    def get_output_shape_for(self, input_shape):
        #for i in range(-self.layerbefore):
        #    tmp = tmp.previous
        tmp_output_shape = self.destin_shape
        if self.dim_ordering == 'th':
            destsize = tmp_output_shape[2:5]
        elif self.dim_ordering == 'tf':
            destsize = tmp_output_shape[1:4]
        width  =  destsize[0]
        height =  destsize[1]
        depth  =  destsize[2]
        if self.dim_ordering == 'th':
            return (input_shape[0],
                    input_shape[1],
                    width,
                    height,
                    depth
                    )
        elif self.dim_ordering == 'tf':
            return (input_shape[0],
                    width,
                    height,
                    depth,
                    input_shape[3])
        else:
            raise Exception('Invalid dim_ordering: ' + self.dim_ordering)

    def call(self, X,  mask=None):
        input_shape =  list(K.shape(X))
        tmp_output_shape = list(self.destin_shape)
        if self.dim_ordering == 'th':
            destsize = tmp_output_shape[2:4]
        elif self.dim_ordering == 'tf':
            destsize = tmp_output_shape[1:3]

        if self.dim_ordering == 'th':
            destsize = list(destsize)
            row_residual = (destsize[0] - input_shape[2])
            col_residual = (destsize[1] - input_shape[3])
            dep_residual = (destsize[2] - input_shape[4])

        elif self.dim_ordering == 'tf':
            row_residual = (destsize[0] - input_shape[1])
            col_residual = (destsize[1] - input_shape[2])
            dep_residual = (destsize[2] - input_shape[3])

        padding = [row_residual//2,col_residual//2, dep_residual//2, row_residual - row_residual//2,  col_residual - col_residual//2, dep_residual - dep_residual//2]
        cropping = [(-row_residual)//2, (-col_residual)//2, (-dep_residual)//2, -(row_residual + (-row_residual)//2),  -(col_residual + (-col_residual)//2), -(dep_residual + (-dep_residual)//2)]
        #result = K.ifelse(K.gt(row_residual, 0), K.spatial_2d_padding_4specify(X, padding = padding), K.spatial_2d_cropping_4specify(X, cropping = cropping))
        result = K.spatial_3d_padding_6specify(X, padding = padding)
        #result = theano.printing.Print('Finish calculating resize')(result + 1)
        return result

    def get_config(self):
        config = {'name': self.__class__.__name__,
                  }
        base_config = super(Resize3D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class Resize2D(Layer):
    '''cropping layer for fully convolutional layer for 2D image(e.g. picture).
    # Input shape
        4D tensor with shape:
        (samples, depth, first_axis_to_pad, second_axis_to_pad)
    # Output shape
        4D tensor with shape:
        (samples, depth, first_padded_axis, second_padded_axis)
    # Arguments
        padding: tuple of int (length 2)
            How many zeros to add at the beginning and end of
            the 2 padding dimensions (axis 3 and 4).
    '''


    def __init__(self, destin_shape = None,input_tensor=None ,dim_ordering='th', input_ndim=4, **kwargs):
        super(Resize2D, self).__init__(**kwargs)

        assert dim_ordering in {'tf', 'th'}, 'dim_ordering must be in {tf, th}'
        self.dim_ordering = dim_ordering
        #self.layerbefore = tuple(layerbefore) # -1 means the previous layer
        if input_tensor is not None:
            self.destin_shape = K.shape(input_tensor)
            if hasattr(input_tensor, '_keras_shape'):
                self.input_keras_shape = input_tensor._keras_shape  
            else:
                self.input_keras_shape = tuple([None, None, None, None])
        else:
            self.input_keras_shape = tuple([None, None, None, None])

            assert destin_shape is not None, 'Please specify the destination shape'
            self.destin_shape = destin_shape
        
        self.input_spec = [InputSpec(ndim=input_ndim)]

    def get_output_shape_for(self, input_shape):
        #for i in range(-self.layerbefore):
        #    tmp = tmp.previous
        tmp_output_shape = self.destin_shape
        if self.dim_ordering == 'th':
            destsize = self.input_keras_shape[2:4]
        elif self.dim_ordering == 'tf':
            destsize = self.input_keras_shape[1:3]
        width =  destsize[0]
        height = destsize[1]
        if self.dim_ordering == 'th':
            return (input_shape[0],
                    input_shape[1],
                    width,
                    height)
        elif self.dim_ordering == 'tf':
            return (input_shape[0],
                    width,
                    height,
                    input_shape[3])

    def call(self, X,  mask=None):
        input_shape =  K.shape(X)
        tmp_output_shape = self.destin_shape
        if self.dim_ordering == 'th':
            destsize = tmp_output_shape[2:4]
        elif self.dim_ordering == 'tf':
            destsize = tmp_output_shape[1:3]

        if self.dim_ordering == 'th':
            #destsize = list(destsize)
            row_residual = (destsize[0] - input_shape[2])
            col_residual = (destsize[1] - input_shape[3])

        elif self.dim_ordering == 'tf':
            row_residual = (destsize[0] - input_shape[1])
            col_residual = (destsize[1] - input_shape[2])
        padding = [row_residual//2,col_residual//2,  row_residual - row_residual//2,  col_residual - col_residual//2]
        cropping = [(-row_residual)//2, (-col_residual)//2,  -(row_residual + (-row_residual)//2),  -(col_residual + (-col_residual)//2)]
        #result = K.ifelse(K.gt(row_residual, 0), K.spatial_2d_padding_4specify(X, padding = padding), K.spatial_2d_cropping_4specify(X, cropping = cropping))
        result = K.spatial_2d_padding_4specify(X, padding = padding)
        #result = theano.printing.Print('Finish calculating resize')(result + 1)
        return result

    def get_config(self):
        config = {'name': self.__class__.__name__,
                  }
        base_config = super(Resize2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))       


class Cropping1D(Layer):
    '''Cropping layer for 1D input (e.g. temporal sequence).
    It crops along the time dimension (axis 1).

    # Arguments
        cropping: tuple of int (length 2)
            How many units should be trimmed off at the beginning and end of
            the cropping dimension (axis 1).

    # Input shape
        3D tensor with shape (samples, axis_to_crop, features)

    # Output shape
        3D tensor with shape (samples, cropped_axis, features)
    '''

    def __init__(self, cropping=(1, 1), **kwargs):
        super(Cropping1D, self).__init__(**kwargs)
        self.cropping = tuple(cropping)
        if len(self.cropping) != 2:
            raise ValueError('`cropping` must be a tuple length of 2.')
        self.input_spec = [InputSpec(ndim=3)]

    def build(self, input_shape):
        self.input_spec = [InputSpec(shape=input_shape)]
        self.built = True

    def get_output_shape_for(self, input_shape):
        if input_shape[1] is not None:
            length = input_shape[1] - self.cropping[0] - self.cropping[1]
        else:
            length = None
        return (input_shape[0],
                length,
                input_shape[2])

    def call(self, x, mask=None):
        input_shape = self.input_spec[0].shape
        return x[:, self.cropping[0]:input_shape[1]-self.cropping[1], :]

    def get_config(self):
        config = {'cropping': self.cropping}
        base_config = super(Cropping1D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


class Cropping2D(Layer):
    '''Cropping layer for 2D input (e.g. picture).
    It crops along spatial dimensions, i.e. width and height.

    # Arguments
        cropping: tuple of tuple of int (length 2)
            How many units should be trimmed off at the beginning and end of
            the 2 cropping dimensions (width, height).
        dim_ordering: 'th' or 'tf'.
            In 'th' mode, the channels dimension (the depth)
            is at index 1, in 'tf' mode is it at index 3.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".

    # Input shape
        4D tensor with shape:
        (samples, depth, first_axis_to_crop, second_axis_to_crop)

    # Output shape
        4D tensor with shape:
        (samples, depth, first_cropped_axis, second_cropped_axis)

    # Examples

    ```python
        # Crop the input 2D images or feature maps
        model = Sequential()
        model.add(Cropping2D(cropping=((2, 2), (4, 4)), input_shape=(3, 28, 28)))
        # now model.output_shape == (None, 3, 24, 20)
        model.add(Convolution2D(64, 3, 3, border_mode='same))
        model.add(Cropping2D(cropping=((2, 2), (2, 2))))
        # now model.output_shape == (None, 64, 20, 16)

    ```

    '''

    def __init__(self, cropping=((0, 0), (0, 0)), dim_ordering='default', **kwargs):
        super(Cropping2D, self).__init__(**kwargs)
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()
        self.cropping = tuple(cropping)
        if len(self.cropping) != 2:
            raise ValueError('`cropping` must be a tuple length of 2.')
        if len(self.cropping[0]) != 2:
            raise ValueError('`cropping[0]` must be a tuple length of 2.')
        if len(self.cropping[1]) != 2:
            raise ValueError('`cropping[1]` must be a tuple length of 2.')
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=4)]

    def build(self, input_shape):
        self.input_spec = [InputSpec(shape=input_shape)]
        self.built = True

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            return (input_shape[0],
                    input_shape[1],
                    input_shape[2] - self.cropping[0][0] - self.cropping[0][1],
                    input_shape[3] - self.cropping[1][0] - self.cropping[1][1])
        elif self.dim_ordering == 'tf':
            return (input_shape[0],
                    input_shape[1] - self.cropping[0][0] - self.cropping[0][1],
                    input_shape[2] - self.cropping[1][0] - self.cropping[1][1],
                    input_shape[3])
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        input_shape = self.input_spec[0].shape
        if self.dim_ordering == 'th':
            return x[:,
                     :,
                     self.cropping[0][0]:input_shape[2]-self.cropping[0][1],
                     self.cropping[1][0]:input_shape[3]-self.cropping[1][1]]
        elif self.dim_ordering == 'tf':
            return x[:,
                     self.cropping[0][0]:input_shape[1]-self.cropping[0][1],
                     self.cropping[1][0]:input_shape[2]-self.cropping[1][1],
                     :]

    def get_config(self):
        config = {'cropping': self.cropping}
        base_config = super(Cropping2D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))

class Cropping3D(Layer):
    '''Cropping layer for 3D data (e.g. spatial or spatio-temporal).

    # Arguments
        cropping: tuple of tuple of int (length 3)
            How many units should be trimmed off at the beginning and end of
            the 3 cropping dimensions (kernel_dim1, kernel_dim2, kernerl_dim3).
        dim_ordering: 'th' or 'tf'.
            In 'th' mode, the channels dimension (the depth)
            is at index 1, in 'tf' mode is it at index 4.
            It defaults to the `image_dim_ordering` value found in your
            Keras config file at `~/.keras/keras.json`.
            If you never set it, then it will be "tf".

    # Input shape
        5D tensor with shape:
        (samples, depth, first_axis_to_crop, second_axis_to_crop, third_axis_to_crop)

    # Output shape
        5D tensor with shape:
        (samples, depth, first_cropped_axis, second_cropped_axis, third_cropped_axis)

    '''

    def __init__(self, cropping=((1, 1), (1, 1), (1, 1)),
                 dim_ordering='default', **kwargs):
        super(Cropping3D, self).__init__(**kwargs)
        if dim_ordering == 'default':
            dim_ordering = K.image_dim_ordering()
        self.cropping = tuple(cropping)
        if len(self.cropping) != 3:
            raise ValueError('`cropping` must be a tuple length of 3.')
        if len(self.cropping[0]) != 2:
            raise ValueError('`cropping[0]` must be a tuple length of 2.')
        if len(self.cropping[1]) != 2:
            raise ValueError('`cropping[1]` must be a tuple length of 2.')
        if len(self.cropping[2]) != 2:
            raise ValueError('`cropping[2]` must be a tuple length of 2.')
        if dim_ordering not in {'tf', 'th'}:
            raise ValueError('dim_ordering must be in {tf, th}.')
        self.dim_ordering = dim_ordering
        self.input_spec = [InputSpec(ndim=5)]

    def build(self, input_shape):
        self.input_spec = [InputSpec(shape=input_shape)]
        self.built = True

    def get_output_shape_for(self, input_shape):
        if self.dim_ordering == 'th':
            dim1 = input_shape[2] - self.cropping[0][0] - self.cropping[0][1] if input_shape[2] is not None else None
            dim2 = input_shape[3] - self.cropping[1][0] - self.cropping[1][1] if input_shape[3] is not None else None
            dim3 = input_shape[4] - self.cropping[2][0] - self.cropping[2][1] if input_shape[4] is not None else None
            return (input_shape[0],
                    input_shape[1],
                    dim1,
                    dim2,
                    dim3)
        elif self.dim_ordering == 'tf':
            dim1 = input_shape[1] - self.cropping[0][0] - self.cropping[0][1] if input_shape[1] is not None else None
            dim2 = input_shape[2] - self.cropping[1][0] - self.cropping[1][1] if input_shape[2] is not None else None
            dim3 = input_shape[3] - self.cropping[2][0] - self.cropping[2][1] if input_shape[3] is not None else None
            return (input_shape[0],
                    dim1,
                    dim2,
                    dim3,
                    input_shape[4])
        else:
            raise ValueError('Invalid dim_ordering:', self.dim_ordering)

    def call(self, x, mask=None):
        input_shape = self.input_spec[0].shape
        if self.dim_ordering == 'th':
            return x[:,
                     :,
                     self.cropping[0][0]:input_shape[2]-self.cropping[0][1],
                     self.cropping[1][0]:input_shape[3]-self.cropping[1][1],
                     self.cropping[2][0]:input_shape[4]-self.cropping[2][1]]
        elif self.dim_ordering == 'tf':
            return x[:,
                     self.cropping[0][0]:input_shape[1]-self.cropping[0][1],
                     self.cropping[1][0]:input_shape[2]-self.cropping[1][1],
                     self.cropping[2][0]:input_shape[3]-self.cropping[2][1],
                     :]

    def get_config(self):
        config = {'cropping': self.cropping}
        base_config = super(Cropping3D, self).get_config()
        return dict(list(base_config.items()) + list(config.items()))


# Aliases

Conv1D = Convolution1D
Conv2D = Convolution2D
Conv3D = Convolution3D
Deconv2D = Deconvolution2D
AtrousConv1D = AtrousConvolution1D
AtrousConv2D = AtrousConvolution2D
SeparableConv2D = SeparableConvolution2D

