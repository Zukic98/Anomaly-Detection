import numpy as np

import _Utils.Color            as C
from   _Utils.Color import prntC
import _Utils.FeatureGetter    as FG
import _Utils.geographic_maths as GEO
import _Utils.plotADSB         as PLT
from   _Utils.Typing import NP, AX

import D_DataLoader.Utils      as U


# |====================================================================================================================
# | CHECKING CLEANESS FOR TRAINING DATA
# |====================================================================================================================


def check_sample(CTX:"dict[str, object]", x:"np.ndarray", i:int, t:int) -> bool:
    lats = FG.lat(x[i])
    lons = FG.lon(x[i])
    HORIZON = CTX["HORIZON"]

    if (lats[t] == 0 and lons[t] == 0):
        return False
    if (lats[t+HORIZON] == 0 and lons[t+HORIZON] == 0):
        return False

    # Check there is no missing timestamp between last timestamp t and prediction timestamp t+HORIZON
    ts_actu = FG.timestamp(x[i][t])
    ts_pred = FG.timestamp(x[i][t+HORIZON])
    if (ts_actu + HORIZON != ts_pred):
        return False

    # Check there is no abnormal distance between two consecutive points (only at the end of the trajectory)
    for t in range(t - CTX["DILATION_RATE"] + 1, t + HORIZON + 1):
        d = GEO.distance(lats[t-1], lons[t-1], lats[t], lons[t])
        if (d > 200 or d < 1.0):
            return False

    return True


# |====================================================================================================================
# | BATCH GENERATION
# |====================================================================================================================

def alloc_sample(CTX:dict)\
        -> "NP.float32_2d[AX.time, AX.feature]":

    x_sample = np.zeros((CTX["INPUT_LEN"],CTX["FEATURES_IN"]))
    return x_sample

def alloc_batch(CTX:dict, size:int) -> """tuple[
        NP.float32_3d[AX.batch, AX.time, AX.feature],
        NP.float32_2d[AX.batch, AX.feature]]""":

    x_batch = np.zeros((size, CTX["INPUT_LEN"],CTX["FEATURES_IN"]))
    y_batch = np.zeros((size, CTX["FEATURES_OUT"]))
    return x_batch, y_batch

def gen_random_sample(CTX:dict, x:"list[NP.float32_2d[AX.time, AX.feature]]", PAD:NP.float32_1d)\
        -> "tuple[NP.float32_2d[AX.time, AX.feature], NP.float32_1d[AX.feature], tuple[float, float]]":
    i, t = pick_random_loc(CTX, x)
    x_sample, y_sample, _, origin = gen_sample(CTX, x, PAD, i, t, valid=True)
    y_sample = FG.lat_lon(y_sample)
    return x_sample, y_sample, origin

def pick_random_loc(CTX:dict, x:"list[NP.float32_2d[AX.time, AX.feature]]") -> "tuple[int, int]":
    HORIZON = CTX["HORIZON"]
    flight_i = np.random.randint(0, len(x))
    t = np.random.randint(0, len(x[flight_i])-HORIZON)

    while not(check_sample(CTX, x, flight_i, t)):
        flight_i = np.random.randint(0, len(x))
        t = np.random.randint(0, len(x[flight_i])-HORIZON)

    return flight_i, t



def gen_sample(CTX:dict,
               x:"list[NP.float32_2d[AX.time, AX.feature]]",
               PAD:NP.float32_1d,
               i:int, t:int, valid:bool=None)\
        -> """tuple[NP.float32_2d[AX.time, AX.feature],
                    NP.float32_1d[AX.feature],
                    bool, tuple[float, float]]""":

    if (valid is None): valid = check_sample(CTX, x, i, t)
    x_sample = alloc_sample(CTX)
    if (not(valid)): return x_sample


    start, end, length, pad_lenght, shift = U.window_slice(CTX, t)
    x_sample[pad_lenght:] = x[i][start:end:CTX["DILATION_RATE"]]
    x_sample[:pad_lenght] = PAD

    last_message = U.get_aircraft_last_message(CTX, x_sample)
    lat, lon = FG.lat(last_message), FG.lon(last_message)
    #TODO remove this check
    if (lat == FG.lat(PAD) or lon == FG.lon(PAD)):
        prntC(C.ERROR, "ERROR: lat or lon is 0")
        prntC(list(range(start, end, CTX["DILATION_RATE"])))
        prntC(FG.lat(x[i][start:end]))
        prntC(i, t, start, end, length, pad_lenght, shift)
        prntC(C.ERROR, "ERROR: lat or lon is 0")

    y_sample = x[i][t+CTX["HORIZON"]]

    x_sample, y_sample = U.batch_preprocess(CTX, x_sample, PAD,
                                 post_flight = np.array([y_sample]))

    return x_sample, y_sample[0], valid, (lat, lon)





