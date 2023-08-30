
from . import CTX
from . import DefaultCTX as default_CTX

import pandas as pd
import numpy as np

from .module import module_to_dict
from .save import load

from .model import Model
from .dataloader import DataLoader
from .MinMaxScaler3D import MinMaxScaler3D
from .SparceLabelBinarizer import SparceLabelBinarizer
from .Utils import batchPreProcess

import pickle

import os

import warnings
warnings.filterwarnings("ignore")

HERE = os.path.abspath(os.path.dirname(__file__))

# Convert CTX to dict and log it
CTX = module_to_dict(CTX)
if (default_CTX != None):
    default_CTX = module_to_dict(default_CTX)
    for param in default_CTX:
        if (param not in CTX):
            CTX[param] = default_CTX[param]


model = Model(CTX)
xScaler = MinMaxScaler3D()
yScaler = SparceLabelBinarizer()



print("Loading weights, please wait...")

# check if .b files exist
if (not os.path.isfile(HERE + "/w.b")):
    w = load(HERE + "/w")
    xs = load(HERE + "/xs")
    ys = load(HERE + "/ys")
    ys = [int(y) for y in ys]

    # save w
    pickle.dump(w, open(HERE + "/w.b", "wb"))
    pickle.dump(xs, open(HERE + "/xs.b", "wb"))
    pickle.dump(ys, open(HERE + "/ys.b", "wb"))
else:
    w = pickle.load(open(HERE + "/w.b", "rb"))
    xs = pickle.load(open(HERE + "/xs.b", "rb"))
    ys = pickle.load(open(HERE + "/ys.b", "rb"))


model.setVariables(w)
xScaler.setVariables(xs)
yScaler.fit(ys)

print("Weights loaded")


def __preprocess__(timestamp,latitude,longitude,groundspeed,track,vertical_rate,onground,alert,spi,squawk,altitude,geoaltitude):

    df = pd.DataFrame(
        {
            "timestamp": timestamp,
            "latitude": latitude,
            "longitude": longitude,
            "groundspeed": groundspeed,
            "track": track,
            "vertical_rate": vertical_rate,
            "onground": onground,
            "alert": alert,
            "spi": spi,
            "squawk": squawk,
            "altitude": altitude,
            "geoaltitude": geoaltitude,
        }
    )


    array = DataLoader.__csv2array__(df, CTX)
    array = array[CTX["DILATION_RATE"]-1::CTX["DILATION_RATE"]]
    return array















class CONTEXT:
    HISTORY = CTX["HISTORY"]
    FEATURES_IN = CTX["FEATURES_IN"]
    FEATURES_OUT = CTX["FEATURES_OUT"]

    LABEL_NAMES = CTX["LABEL_NAMES"]
    # LABEL_ID = CTX["LABEL_FILTER"]
    BOUNDING_BOX = CTX["BOUNDING_BOX"]






def predictAircraftType(timestamp,latitude,longitude,groundspeed,track,vertical_rate,onground,alert,spi,squawk,altitude,geoaltitude,):
    """
    Make predicitons of aircraft type based on ADS-B/FLARM features.

    Each feature is an array of shape [?, HISTORY].

    return : probability array of shape [?, FEATURES_OUT]
    """

    # check the features
    for f in [timestamp,latitude,longitude,groundspeed,track,vertical_rate,onground,alert,spi,squawk,altitude,geoaltitude]:

        assert len(f) == len(timestamp), 'all features must have the same number of samples'

        for i in range(len(f)):
            assert len(f[i]) == CTX['HISTORY'], 'all features must have the a length shape of [?, ' + str(CTX['HISTORY'])+"]"

    np_array = np.array([
        __preprocess__(timestamp[i],
                   latitude[i],
                   longitude[i],
                   groundspeed[i],
                   track[i],
                   vertical_rate[i],
                   onground[i],
                   alert[i],spi[i],
                   squawk[i],altitude[i],
                   geoaltitude[i]) 
            for i in range(len(timestamp))
        ])

    x_glob = np_array
    y_glob = np.zeros((len(x_glob), CTX["FEATURES_OUT"]))

    MAX_BATCH_SIZE = 64
    for i in range(0, len(x_glob), MAX_BATCH_SIZE):
        x = x_glob[i:i+MAX_BATCH_SIZE]

        if ("img" in model.name):
            # gen geogaphic map
            img = np.array([DataLoader.genImg(
                    xi[-1][CTX["FEATURE_MAP"]["latitude"]], 
                    xi[-1][CTX["FEATURE_MAP"]["longitude"]], 
                    CTX["IMG_SIZE"]) for xi in x]) / 255.0

        x = [batchPreProcess(CTX, flight) for flight in x]
        x = np.array(xScaler.transform(x))

        if ("img" in model.name):
            y = model.predict(x, img)
        else:
            y = model.predict(x)

        y_glob[i:i+MAX_BATCH_SIZE] = y


    return y_glob

def probabilityToLabel(proba):
    """
    Take an array of probabilities and give the label
    corresponding to the highest class.

    proba : probabilities, array of shape : [?, FEATURES_OUT]

    return : label id, array of int, shape : [?]
    """
    i = np.argmax(proba, axis=1)
    l = yScaler.classes_[i]
    return l

def labelToName(label) -> "list[str]" :
    """
    Give the label name (easily readable for humman) 
    according to the label id.

    label : label id, array of int, shape : [?]

    return : classes names, array of string, shape : [?]
    """
    return [CTX["LABEL_NAMES"][l] for l in label]





