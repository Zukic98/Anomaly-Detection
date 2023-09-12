import numpy as np
import math
import pandas as pd
import os
from PIL import Image
from _Utils import Color


def batchPreProcess(CTX, flight, relative_position=False, relative_heading=False, random_heading=False):
    """
    Additional method of preprocessing after
    batch generation.

    Normalize lat, lon of a flight fragment to 0, 0.
    Rotate the fragment with a random angle to avoid
    biais of the model.
 
    Parameters:
    -----------

    flight: np.array
        A batch of flight fragment

    Returns:
    --------

    flight: np.array
        Same batch but preprocessed


    """
    # Get the index of each feature by name for readability
    FEATURE_MAP = CTX["FEATURE_MAP"]
    lat = flight[:, FEATURE_MAP["latitude"]]
    lon = flight[:, FEATURE_MAP["longitude"]]
    heading = flight[:, FEATURE_MAP["track"]]
    baro_altitude = flight[:, FEATURE_MAP["altitude"]]
    geo_altitude = flight[:, FEATURE_MAP["geoaltitude"]]
    groundspeed = flight[:, FEATURE_MAP["groundspeed"]]



    # do not change angle, and rotate the whole bounding box to 0, 0 (not relative just normalizing)
    R = 0
    Y = CTX["BOX_CENTER"][0]
    Z = -CTX["BOX_CENTER"][1]

    if relative_position:
        # R = heading[-1]
        Y = lat[-1]
        Z = -lon[-1]

    
    if relative_heading:
        R = heading[-1]

    if random_heading:
        R = np.random.uniform(0, 360)

    # Normalize lat lon to 0, 0
    # Convert lat lon to cartesian coordinates
    x = np.cos(np.radians(lon)) * np.cos(np.radians(lat))
    y = np.sin(np.radians(lon)) * np.cos(np.radians(lat))
    z =                           np.sin(np.radians(lat))

    # Normalize longitude with Z rotation
    r = np.radians(Z)
    xz = x * np.cos(r) - y * np.sin(r)
    yz = x * np.sin(r) + y * np.cos(r)
    zz = z

    # Normalize latitude with Y rotation
    r = np.radians(Y)
    xy = xz * np.cos(r) + zz * np.sin(r)
    yy = yz
    zy = -xz * np.sin(r) + zz * np.cos(r)

    # Rotate the fragment with the random angle along X axis
    r = np.radians(R)
    xx = xy
    yx = yy * np.cos(r) - zy * np.sin(r)
    zx = yy * np.sin(r) + zy * np.cos(r)

    # convert back cartesian to lat lon
    lat = np.degrees(np.arcsin(zx))
    lon = np.degrees(np.arctan2(yx, xx))

    # rotate heading as well
    heading = heading - R
    heading = np.remainder(heading, 360)

    # print(lat[-10:], lon[-10:], heading[-10:], sep="\n\n")
    # exit(0)
    

    # Normalise altitude 
    # peharps not a good idea because vertrate is already 
    # kind of normalized
    # baro_altitude = baro_altitude - baro_altitude[-1]
    # geo_altitude = geo_altitude - geo_altitude[-1]

    if (relative_position):
        # if we use relative position, and the begining of the fragment is padding
        # (detected thanks to the ground speed = -1)
        # we shound not use the relative position for the padding
        # so each lat lon where ground speed is -1 is set to 0, 0
        lat = np.where(groundspeed == -1, 0, lat)
        lon = np.where(groundspeed == -1, 0, lon)
    
    flight[:, FEATURE_MAP["latitude"]] = lat
    flight[:, FEATURE_MAP["longitude"]] = lon
    flight[:, FEATURE_MAP["track"]] = heading
    # To imlement and test : Heading 180
    # Add header 180 to remove the gap between 0 and 360
    # of the original heading feature.
    # flight[:, FEATURE_MAP["heading180"]] = heading180
    flight[:, FEATURE_MAP["altitude"]] = baro_altitude
    flight[:, FEATURE_MAP["geoaltitude"]] = geo_altitude
    

    return flight
    



def add_noise(flight, label, noise, noised_label_min=0.5):
    """Add same noise to the x and y to reduce bias but 
    mostly to have a more linear output probabilites meaning :
    - avoid to have 1 or 0 prediction but more something
    like 0.3 or 0.7.
    """

    if (noise > 1.0):
        print("ERROR: noise must be between 0 and 1")
        # throw error
        raise ValueError
    if (noise <= 0.0):
        return flight, label

    noise_strength = np.random.normal(0, noise)
    # noise_strength = np.random.uniform(0, noise)

    flight_noise = np.random.uniform(-noise_strength, noise_strength, size=flight.shape)
    flight = flight + flight_noise


    effective_strength = noise_strength / noise
    label = label * (1 - effective_strength * (1-noised_label_min))

    return flight, label



"""
UTILITARY FUNCTION FOR MAP PROJECTION
Compute the pixel coordinates of a given lat lon into map.png
"""
def deg2num_int(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = ((lon_deg + 180.0) / 360.0 * n)
    ytile = ((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)




def dfToFeatures(df, CTX):
    """
    Convert a complete ADS-B trajectory dataframe into a numpy array
    with the right features and preprocessing
    """

    if (CTX["PAD_MISSING_INPUT_LEN"]):
        i = 0
        while (i < len(df)-1):
            if (df["timestamp"].iloc[i+1] != df["timestamp"].iloc[i]+1):
                nb_row_to_add = df["timestamp"].iloc[i+1] - df["timestamp"].iloc[i] - 1

                sub_df = pd.DataFrame([df.iloc[i]]*nb_row_to_add)
                sub_df["timestamp"] = np.arange(df["timestamp"].iloc[i] + 1, df["timestamp"].iloc[i+1])

                df = pd.concat([df.iloc[:i+1], sub_df, df.iloc[i+1:]]).reset_index(drop=True)

                i += nb_row_to_add
            i += 1

    # add sec (60), min (60), hour (24) and day_of_week (7) features
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df["sec"] = df["timestamp"].dt.second
    df["min"] = df["timestamp"].dt.minute
    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.dayofweek

    # remove too short flights
    if (len(df) < CTX["HISTORY"]):
        print(df["callsign"][0], df["icao24"][0], "is too short")
        return []

    # Cast booleans into numeric
    for col in df.columns:
        if (df[col].dtype == bool):
            df[col] = df[col].astype(int)

    
    # Remove useless columns
    df = df[CTX["USED_FEATURES"]]

        
    # Fill NaN with -1
    df = df.fillna(-1)
    np_array = df.to_numpy().astype(np.float32)
    return np_array


__icao_db__ = None
def getLabel(CTX, icao, callsign):
    """
    Give the label of an aircraft based on his icao imatriculation
    """
    global __icao_db__
    if __icao_db__ is None:
        labels_file = os.path.join("./A_Dataset/AircraftClassification/labels.csv")
        __icao_db__ = pd.read_csv(labels_file, sep=",", header=None, dtype={"icao24":str})
        __icao_db__.columns = ["icao24", "label"]
        __icao_db__ = __icao_db__.fillna("NULL")


        # merge labels asked as similar
        for label in CTX["MERGE_LABELS"]:
            __icao_db__["label"] = __icao_db__["label"].replace(CTX["MERGE_LABELS"][label], label)

        # to dict
        __icao_db__ = __icao_db__.set_index("icao24").to_dict()["label"]

    if (12 in CTX["MERGE_LABELS"] and callsign.startswith("SAMU")):
        return 12

    if (icao in __icao_db__):
        return __icao_db__[icao]
    
    print("[Warning]", icao, "not found in labels.csv")
    
    return 0

# load image as numpy array
path = "A_Dataset/AircraftClassification/map.png"
img = Image.open(path)
MAP =  np.array(img, dtype=np.float32)
def genMap(lat, lon, size):
    """Generate an image of the map with the flight at the center"""


    #######################################################
    # Convert lat, lon to px
    # thoses param are constants used to generate the map 
    zoom = 13
    min_lat, min_lon, max_lat, max_lon = 43.01581, 0.62561,  44.17449, 2.26344
    # conversion
    xmin, ymax = deg2num_int(min_lat, min_lon, zoom)
    xmax, ymin = deg2num_int(max_lat, max_lon, zoom)
    #######################################################

    x_center, y_center = deg2num(lat, lon, zoom)

    x_center = (x_center-xmin)*255
    y_center = (y_center-ymin)*255


    x_min = int(x_center - (size / 2.0))
    x_max = int(x_center + (size / 2.0))
    y_min = int(y_center - (size / 2.0))
    y_max = int(y_center + (size / 2.0))

    if (x_min < 0):
        x_max = size
        x_min = 0
    elif (x_max > MAP.shape[1]):
        x_max = MAP.shape[1]
        x_min = MAP.shape[1] - size

    elif (y_min < 0):
        y_max = size
        y_min = 0
    elif (y_max > MAP.shape[0]):
        y_max = MAP.shape[0]
        y_min = MAP.shape[0] - size
    
    
    img = MAP[
        y_min:y_max,
        x_min:x_max, :]
    
    return img






def compute_shift(start, end, dilatation):
    """
    compute needed shift to have the last timesteps at the end of the array
    """

    d = end - start
    shift = (d - (d // dilatation) * dilatation - 1) % dilatation
    return shift



def pick_an_interesting_aircraft(CTX, x, y, label, n=1):
    flight_i = -1
    while flight_i == -1 or y[flight_i, label] != 1:
        flight_i = np.random.randint(0, len(x))
    # pick a timestep in the flight (if negative, the fragment is not yet full of timesteps -> padding)
    negative = np.random.randint(0, 100) <= 1000
    if (negative):
        time_step = np.random.randint(0, CTX["HISTORY"]-1)
    else:
        time_step = np.random.randint(CTX["HISTORY"]-1, len(x[flight_i])-(n-1))

    return flight_i, np.arange(time_step, time_step+n)

def to_scientific_notation(number):
    """"
    compute n the value and e the exponent
    """
    if (np.isnan(number)):
        return np.nan, 0
    e = 0
    if (number != 0):
        e = math.floor(math.log10(abs(number)))
        n = number / (10**e)
    else:
        n = 0
    return n, e

def round_to_first_non_zero(number):
    if (number == 0):
        return 0
    n, e = to_scientific_notation(number)
    if (e >= 0):
        return round(number, 1)
    if (e <= -10):
        return round(number, 0)
    
    return round(number, -e)

def round_to_first_non_zero_array(array):
    for i in range(len(array)):
        for j in range(len(array[i])):
            array[i][j] = round_to_first_non_zero(array[i][j])
    return array

def print_2D_timeserie(CTX, array, max_len=10):
    """
    shape : [time_step, feature]
    """
    # round numbers to the first non zero decimal
    array = round_to_first_non_zero_array(array)
    array = array.astype(str)
    # remove ending .0
    for i in range(len(array)):
        for j in range(len(array[i])):
            while ("." in array[i][j] and array[i][j].endswith("0")):
                array[i][j] = array[i][j][:-1]
            if (array[i][j].endswith(".")):
                array[i][j] = array[i][j][:-1]
            if (array[i][j].startswith("-0.") or array[i][j] == "-0"):
                array[i][j] = array[i][j][1:]

    max_length = []

    # header
    for i in range(CTX["FEATURES_IN"]):
        # length
        max_feature_length = max([len(array[t][i]) for t in range(len(array))])
        max_length.append(max(max_feature_length, len(CTX["USED_FEATURES"][i])))

    # print header
    for i in range(CTX["FEATURES_IN"]):
        print(Color.GREEN + CTX["USED_FEATURES"][i].ljust(max_length[i]) + Color.RESET, end="|" if i < CTX["FEATURES_IN"]-1 else "\n")


    indexs = np.arange(0, len(array))
    if (len(array) > max_len):
        half = (max_len + 1) // 2
        indexs = np.concatenate([indexs[:half], [-1], indexs[-half:]])

    for t in indexs:
        if (t == -1):
            print("...".rjust(max_length[0]), end="|" if i < CTX["FEATURES_IN"]-1 else "\n")
            continue
        for i in range(CTX["FEATURES_IN"]):
            print(array[t][i].rjust(max_length[i]), end="|" if i < CTX["FEATURES_IN"]-1 else "\n")
    print()