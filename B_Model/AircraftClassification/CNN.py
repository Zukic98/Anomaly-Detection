
import tensorflow as tf
from keras.layers import *

from B_Model.AbstractModel import Model as AbstactModel
from B_Model.Utils.TF_Modules import *

import numpy as np

import os


class Model(AbstactModel):
    """
    Convolutional neural network model for 
    aircraft classification based on 
    recordings of ADS-B data fragment.

    Parameters:
    ------------

    CTX: dict
        The hyperparameters context


    Attributes:
    ------------

    name: str (MENDATORY)
        The name of the model for mlflow logs
    
    Methods:
    ---------

    predict(x): (MENDATORY)
        return the prediction of the model

    compute_loss(x, y): (MENDATORY)
        return the loss and the prediction associated to x, y and y_

    training_step(x, y): (MENDATORY)
        do one training step.
        return the loss and the prediction of the model for this batch

    visualize(save_path):
        Generate a visualization of the model's architecture
    """

    name = "CNN"

    def __init__(self, CTX:dict):
        """ 
        Generate model architecture
        Define loss function
        Define optimizer
        """


        # load context
        self.CTX = CTX
        self.dropout = CTX["DROPOUT"]
        self.outs = CTX["FEATURES_OUT"]

        # save the number of training steps
        self.nb_train = 0


        x_input_shape = (self.CTX["INPUT_LEN"], self.CTX["FEATURES_IN"])
        if (CTX["ADD_TAKE_OFF_CONTEXT"]): takeoff_input_shape = (self.CTX["INPUT_LEN"], self.CTX["FEATURES_IN"])
        if (CTX["ADD_MAP_CONTEXT"]): map_input_shape = (self.CTX["IMG_SIZE"], self.CTX["IMG_SIZE"], 3)
    
        x = tf.keras.Input(shape=x_input_shape, name='input')
        inputs = [x]
        if (CTX["ADD_TAKE_OFF_CONTEXT"]): 
            takeoff = tf.keras.Input(shape=takeoff_input_shape, name='takeoff')
            inputs.append(takeoff)

        if (CTX["ADD_MAP_CONTEXT"]): 
            map = tf.keras.Input(shape=map_input_shape, name='map')
            inputs.append(map)

        # concat takeoff and x
        if (CTX["ADD_TAKE_OFF_CONTEXT"]): 
            z = Concatenate(axis=2)([x, takeoff])
        else:
            z = x


        if (CTX["ADD_MAP_CONTEXT"]):
            y_map = map

            n=1
            for _ in range(n):
                y_map = Conv2DModule(64, 3, padding="same")(y_map)
            y_map = MaxPooling2D()(y_map)

            for _ in range(n):
                y_map = Conv2DModule(64, 3, padding="same")(y_map)
            y_map = MaxPooling2D()(y_map)

            for _ in range(n):
                y_map = Conv2DModule(128, 3, padding="same")(y_map)
            y_map = GlobalAveragePooling2D()(y_map)
            y_map = Flatten()(y_map)
            y_map = RepeatVector(self.CTX["INPUT_LEN"] // 2)(y_map)


        n = self.CTX["LAYERS"]
        for _ in range(n):
            z = Conv1DModule(128, 3, padding="same")(z)
        z = MaxPooling1D()(z)

        if (CTX["ADD_MAP_CONTEXT"]): z = Concatenate()([z, y_map])

        for _ in range(n):
            z = Conv1DModule(256, 3, padding="same")(z)
        
        z = Conv1DModule(self.outs, 3, padding="same")(z)

        z_ = GlobalAveragePooling1D()(z)
        z = Flatten()(z)


            
        z = Dense(self.outs, activation="softmax")(z)
        y = z * 0.7 + z_ * 0.3
            
            
        self.model = tf.keras.Model(inputs, y)


        # define loss function
        # self.loss = tf.keras.losses.CategoricalCrossentropy()
        self.loss = tf.keras.losses.MeanSquaredError()

        # define optimizer
        self.opt = tf.keras.optimizers.Adam(learning_rate=CTX["LEARNING_RATE"])

        
    def predict(self, x):
        """
        Make prediction for x 
        """
        return self.model(x)

    def compute_loss(self, x, y):
        """
        Make a prediction and compute the loss
        that will be used for training
        """
        y_ = self.model(x)
        return self.loss(y_, y), y_

    def training_step(self, x, y):
        """
        Do one forward pass and gradient descent
        for the given batch
        """
        with tf.GradientTape(watch_accessed_variables=True) as tape:
            loss, output = self.compute_loss(x, y)

            gradients = tape.gradient(loss, self.model.trainable_variables)
            self.opt.apply_gradients(zip(gradients, self.model.trainable_variables))

        self.nb_train += 1
        return loss, output



    def visualize(self, save_path="./_Artefact/"):
        """
        Generate a visualization of the model's architecture
        """
        
            
        filename = os.path.join(save_path, self.name+".png")
        tf.keras.utils.plot_model(self.model, to_file=filename, show_shapes=True)



    def getVariables(self):
        """
        Return the variables of the model
        """
        return self.model.trainable_variables

    def setVariables(self, variables):
        """
        Set the variables of the model
        """
        for i in range(len(variables)):
            self.model.trainable_variables[i].assign(variables[i])
