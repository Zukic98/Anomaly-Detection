
import pandas as pd
import numpy as np

import D_DataLoader.Utils as U
import D_DataLoader.FloodingSolver.Utils as SU
from   D_DataLoader.AbstractDataLoader import DataLoader as AbstractDataLoader

import _Utils.FeatureGetter as FG
import _Utils.Color as C
from   _Utils.Color import prntC
from _Utils import Limits
from   _Utils.Scaler3D import  StandardScaler3D, SigmoidScaler2D, fillNaN3D, fillNaN2D
from   _Utils.ProgressBar import ProgressBar
import _Utils.plotADSB as PLT
from   _Utils.ADSB_Streamer import Streamer
from   _Utils.Typing import NP, AX



# |====================================================================================================================
# | GLOBAL VARIABLES
# |====================================================================================================================

BAR = ProgressBar()
STREAMER = Streamer()


# |====================================================================================================================
# | DATA LOADER
# |====================================================================================================================


# managing the data preprocessing
class DataLoader(AbstractDataLoader):

    x_train:"list[NP.float32_2d[AX.time, AX.feature]]"
    x_test :"list[NP.float32_2d[AX.time, AX.feature]]"

# |====================================================================================================================
# |     INITIALISATION : LOADING RAW DATASET FROM DISK
# |====================================================================================================================

    def __init__(self, CTX:dict, path:str="") -> None:
        self.CTX = CTX
        self.PAD = None

        self.xScaler = StandardScaler3D()
        self.yScaler = SigmoidScaler2D()

        training = (CTX["EPOCHS"] and path != "")
        if (training):
            x = self.__get_dataset__(path)
            self.x_train,self.x_test = self.__split__(x)
        else:
            prntC(C.INFO, "Training, deactivated, only evaluation will be launched.")
            prntC(C.WARNING, "Make sure everything is loaded from the disk, especially the PAD values.")


    def __load_dataset__(self, CTX:dict, path:str) -> "list[NP.float32_2d[AX.time, AX.feature]]":

        filenames = U.list_flights(path, limit=Limits.INT_MAX)
        BAR.reset(max=len(filenames))

        x = []
        for f in range(len(filenames)):
            df = U.read_trajectory(path, filenames[f])
            array = U.df_to_feature_array(CTX, df)
            x.append(array)
            BAR.update(f+1)

        if (self.PAD is None): self.PAD = U.genPadValues(CTX, x)
        x = fillNaN3D(x, self.PAD)

        return x


# |====================================================================================================================
# |    SCALERS
# |====================================================================================================================

    def __scalers_transform__(self, CTX:dict,
                                    x_batch:NP.float32_3d[AX.sample, AX.time, AX.feature],
                                    y_batch:NP.float32_2d[AX.sample, AX.feature]=None) \
            -> """tuple[NP.float32_3d[AX.sample, AX.time, AX.feature], NP.float32_2d[AX.sample, AX.feature]]
                | NP.float32_3d[AX.sample, AX.time, AX.feature]""":

        if (not(self.xScaler.isFitted())):
            self.xScaler.fit(x_batch)
        x_batch = self.xScaler.transform(x_batch)

        if (y_batch is not None):
            if (not(self.yScaler.isFitted())):
                self.yScaler.fit(y_batch)

            y_batch = self.yScaler.transform(y_batch)
            return x_batch, y_batch
        return x_batch



# |====================================================================================================================
# |     UTILS
# |====================================================================================================================

    def __reshape__(self, CTX:dict,
                          x_batch:NP.float32_3d[AX.sample, AX.time, AX.feature],
                          y_batch:NP.float32_2d[AX.sample, AX.feature],
                          nb_batches:int, batch_size:int) -> """tuple[
            NP.float32_4d[AX.batch, AX.sample, AX.time, AX.feature],
            NP.float32_3d[AX.batch, AX.sample, AX.feature]]""":

        x_batches = x_batch.reshape(nb_batches, batch_size, CTX["INPUT_LEN"],CTX["FEATURES_IN"])
        y_batches = y_batch.reshape(nb_batches, batch_size, CTX["FEATURES_OUT"])

        return x_batches, y_batches

# |====================================================================================================================
# |    GENERATE A TRAINING SET
# |====================================================================================================================

    def genEpochTrain(self) -> """tuple[
            NP.float32_4d[AX.batch, AX.sample, AX.time, AX.feature],
            NP.float32_3d[AX.batch, AX.sample, AX.feature]]""":

        CTX = self.CTX

        # Allocate memory for the batches
        x_batch, y_batch = SU.alloc_batch(CTX, CTX["NB_BATCH"] * CTX["BATCH_SIZE"])

        for n in range(len(x_batch)):
            x_sample, y_sample, origin = SU.gen_random_sample(CTX, self.x_train, self.PAD)

            x_batch[n] = x_sample
            y_batch[n] = y_sample

        self.__plot_flight__(x_sample, y_sample, origin)

        x_batch, y_batch = self.__scalers_transform__(CTX, x_batch, y_batch)
        x_batches, y_batches = self.__reshape__(CTX, x_batch, y_batch, CTX["NB_BATCH"], CTX["BATCH_SIZE"])

        return x_batches, y_batches


    def __plot_flight__(self,
                        x:NP.float32_2d[AX.time, AX.feature],
                        y:NP.float32_1d[AX.feature],
                        origin:"tuple[float, float]") -> None:

        NAME = "train_example"
        lat = FG.lat(x)
        lon = FG.lon(x)
        o_lat, o_lon = origin
        lat, lon     = U.denormalize_trajectory( self.CTX, lat, lon, o_lat, o_lon, 0)
        y_lat, y_lon = U.denormalize_trajectory(self.CTX, [y[0]], [y[1]], o_lat, o_lon, 0)

        box = [U.mini(lat, y_lat), U.mini(lon, y_lon), U.maxi(lat, y_lat), U.maxi(lon, y_lon)]
        # add some margin
        size = max(box[2]-box[0], box[3]-box[1])
        box[0] -= size * 0.1
        box[1] -= size * 0.1
        box[2] += size * 0.1
        box[3] += size * 0.1

        PLT.figure (NAME, box[0], box[1], box[2], box[3])
        PLT.title  (NAME, "Flooding Solver - Prediction on a training sample")
        PLT.plot   (NAME, lat, lon, color="tab:blue", linestyle="--")
        PLT.scatter(NAME, lat, lon, color="tab:blue", marker="x")
        PLT.scatter(NAME, y_lat, y_lon, color="tab:green", marker="+")

        PLT.attach_data(NAME+"Origin", (o_lat, o_lon))






# |====================================================================================================================
# |     GENERATE A TEST SET
# |====================================================================================================================

    def genEpochTest(self) -> """tuple[
            NP.float32_4d[AX.batch, AX.sample, AX.time, AX.feature],
            NP.float32_3d[AX.batch, AX.sample, AX.feature]]""":

        CTX = self.CTX
        SIZE =  int(CTX["NB_BATCH"] * CTX["BATCH_SIZE"] * CTX["TEST_RATIO"])

        x_batch, y_batch = SU.alloc_batch(CTX, SIZE)

        for n in range(SIZE):
            x_sample, y_sample, _ = SU.gen_random_sample(CTX, self.x_test, self.PAD)
            x_batch[n] = x_sample
            y_batch[n] = y_sample

        batch_size = min(CTX["MAX_BATCH_SIZE"], len(x_batch))
        nb_batches = len(x_batch) // batch_size

        x_batch, y_batch = self.__scalers_transform__(CTX, x_batch, y_batch)
        x_batches, y_batches = self.__reshape__(CTX, x_batch, y_batch, nb_batches, batch_size)
        return x_batches, y_batches



# |====================================================================================================================
# | STREAMING ADS-B MESSAGE TO EVALUATE THE MODEL UNDER REAL CONDITIONS
# |====================================================================================================================



class StreamerInterface:
    def __init__(self, dl:DataLoader) -> None:
        self.dl = dl
        self.CTX = dl.CTX

    def stream(self, x:"dict[str, object]")\
            -> "tuple[NP.float32_3d[AX.sample, AX.time, AX.feature], bool]":

        MAX_LENGTH_NEEDED = self.CTX["INPUT_LEN"] + self.CTX["HORIZON"]
        MIN_LENGTH_NEEDED = self.CTX["DILATION_RATE"] + 1 + self.CTX["HORIZON"]

        tag = x.get("tag", x["icao24"])
        raw_df = STREAMER.add(x, tag=tag)
        cache = STREAMER.cache("FloodingSolver", tag)

        array = U.df_to_feature_array(self.CTX, raw_df[-2:], check_length=False)
        array = fillNaN2D(array, self.dl.PAD)

        if (cache is not None):
            cache = np.concatenate([cache, array[1:]], axis=0)
            cache = cache[-MAX_LENGTH_NEEDED:]
        else:
            cache = array
        STREAMER.cache("AircraftClassification", tag, cache)

        # |--------------------------
        # | Generate a sample
        x_batch, _ = SU.alloc_batch(self.CTX, 1)

        # set valid to None, mean that we don't know yet
        valid = None
        if (len(cache) < MIN_LENGTH_NEEDED): valid = False

        x_batch[0], valid = SU.gen_sample(self.CTX, [cache], self.dl.PAD, 0, len(cache)-1, valid)
        x_batch, _ = self.dl.__scalers_transform__(self.CTX, x_batch)
        x_batches, _ = self.dl.__reshape__(self.CTX, x_batch, np.zeros((1, self.CTX["FEATURES_OUT"])), 1, 1)
        return x_batches[0], valid



