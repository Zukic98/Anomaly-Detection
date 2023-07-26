
LEARNING_RATE = 0.00006
EPOCHS = 80
BATCH_SIZE = 128
NB_BATCH = 32


HISTORY = 128
DILATION_RATE = 1
TIMESTEPS = HISTORY // DILATION_RATE

RELATIVE_POSITION = True
RELATIVE_HEADING = False
RANDOM_HEADING = False
TRAINING_NOISE = 0.0

USE_CONTEXT = True

# PAD_MISSING_TIMESTEPS = 


LAYERS = 5
UNITS = 128
RESIDUAL = 2
DROPOUT = 0.3


USED_FEATURES = [
    "latitude", "longitude",
    "groundspeed", "track",
    "vertical_rate", "onground",
    "alert", "spi", "squawk",
    "altitude", "geoaltitude",
]
FEATURES_IN = len(USED_FEATURES)
FEATURE_MAP = dict([[USED_FEATURES[i], i] for i in range(len(USED_FEATURES))])

<<<<<<< HEAD
LABEL_FILTER = [
    1, # CARGO
    2, # PLANE
    # 3, # JET
    4, # TURBO PROPELLER
    5, # MEDIUM
    6, # LIGHT
    7, # SUPER LIGHT
    # 8, # GLIDER
    9,  # HELICOPTER
    10,  # ULM
    11 # military 
]

MERGE_LABELS = { # no merge by default
    2: [1, 2, 3, 4], # PLANE
    6: [5, 6, 7, 8, 10], # MEDIUM
    9: [9], # HELICOPTER
    11: [11] # military
}
FEATURES_OUT = len(MERGE_LABELS)
=======

>>>>>>> 99a415dd9fb2d92138b8778b6c7b938262e0b957

# for training a batch concerning a single aircraft flight
# the step is the jump between two consecutive batches
# each element of a batch start at [t, t+STEP, t+2*STEP, ...]
TRAIN_WINDOW = 8
STEP = 2



IMG_SIZE = 128

