
import pandas as pd
import numpy as np
from _Utils.MinMaxScaler3D import MinMaxScaler3D
from _Utils.SparceLabelBinarizer import SparceLabelBinarizer
from D_DataLoader.AbstractDataLoader import DataLoader as AbstractDataLoader
import os
import math
# MultiLabelBinirazer
from sklearn.preprocessing import LabelBinarizer

import matplotlib.pyplot as plt


from D_DataLoader.AircraftClassification.Utils import batchPreProcess, add_noise


# managing the data preprocessing
class DataLoader(AbstractDataLoader):
    """
    Data manager for aircraft classification
    loads ADS-B reccords and format them for training

    Pipeline :
    ----------

    1. Load all the flights in the dataset folder
        one flight = one list of adsb features. (__load_dataset__)

    2. Preprocess flights globaly (__load_dataset__)

    3. Split the dataset into train and test (__init__)

    4. Split training batches (__genEpochTrain__, __genEpochTest__)

    5. Preprocess batches (__genEpochTrain__, __genEpochTest__)

    6. Scale batches


    Parameters :
    ------------

    CTX : dict
        The hyperparameters context

    path : str
        The path to the dataset

        
    Attributes :
    ------------

    xScaler: Scaler
        Scaler for the input data

    yScaler: Scaler
        Scaler for the output data

    x: np.array
        The input data

    y: np.array
        The associated output desired to be predicted

        
    x_train: np.array
        isolated x train dataset

    y_train: np.array
        isolated y train dataset

    x_test: np.array
        isolated x test dataset

    y_test: np.array
        isolated y test dataset
    

    Methods :
    ---------

    static __load_dataset__(CTX, path): x, y
        Read all flights into the defined folder and do some global preprocessing
        as filtering interisting variables, computing some features (eg: vectorial speed repr)

        WARNING :
        This function is generally heavy, and if you want to make
        several training on the same dataset, USE the __get_dataset__ method
        wich save the dataset on the first call and return it on the next calls

        For evaluation, generally the dataset
        you want to use is independant. Hence, you 
        can use the __load_dataset__ method directly on the Eval folder

    __get_dataset__(path): x, y (Inherited)
        Return dataset with caching
        it will save the dataset on the first call and return it on the next calls
        so you MUST ONLY use it on one dataset (generally training dataset)
        

    genEpochTrain(nb_batch, batch_size):
        Generate the x and y input, directly usable by the model.
        Pick randoms flights from train sub-dataset, and takes a
        somes fragements of it to compose batches
    
    genEpochTest():
        Generate the x and y test.
        Pick randoms flights from train sub-dataset, and takes a
        somes fragements of it to compose batches

    genEval(path):
        Load evaluation flights in the folder of desired path.
        Preprocess them same way as training flights, keep the full
        sliding window along the whole flight, and finally
        it keep a trace of the orriginal flight associated with each
        fragment of sliding window to be able to compute the accuracy
        and the final label for the complete flight
    """


    @staticmethod
    def __load_dataset__(CTX, path, files:"list[str]"=None):
        """
        Read all flights into the defined folder and do some global preprocessing
        as filtering interisting variables, computing some features (eg: vectorial speed repr)

        Parameters:
        -----------

        CTX: dict
            The hyperparameters context

        path: str
            The path to the dataset

        Returns:
        --------
        x, y: list(np.array) 
            The input and output data.
            We use list because time series lenght is 
            variable because each flight has a different 
            duration.
        """


        # Load the labelisation.
        # Associate Icao imatriculation to a flight type
        # Labels are :
        # -1 : unknown
        # 0 : unspecified
        # 1 : airplane
        # 2 : "jet"
        # 3 : small aircraft
        # 4 : "glider"
        # 5 : helicopter
        # 6 : very light aircraft
        labels_file = os.path.join(os.path.dirname(path), "labels.csv")
        labels = pd.read_csv(labels_file, sep=",", header=None, dtype={"icao24":str})
        labels.columns = ["icao24", "label"]
        labels = labels.fillna("NULL")


        # Labels 2, 3 and 6 distincion is not relevant
        # so we merge them into one class : 3
        # labels["label"] = labels["label"].replace([2, 3, 6], 3)


        # Loading the flight.

        # List files in the folder
        data_files = os.listdir(path)
        x = []
        y = []

        print("Loading dataset :")

        # Read each file
        for f in range(len(data_files)):
            file = data_files[f]
            # set time as index
            df = pd.read_csv(os.path.join(path, file), sep=",",dtype={"callsign":str, "icao24":str})

            # between each row, if the time value is not +1,
            # padd the dataframe with the first row
            # to have a continuous time series
            if (CTX["PAD_MISSING_TIMESTEPS"]):
                i = 0
                while (i < len(df)-1):
                    if (df["time"].iloc[i+1] != df["time"].iloc[i]+1):
                        nb_row_to_add = df["time"].iloc[i+1] - df["time"].iloc[i] - 1

                        sub_df = pd.DataFrame([df.iloc[i]]*nb_row_to_add)
                        sub_df["time"] = np.arange(df["time"].iloc[i] + 1, df["time"].iloc[i+1])

                        df = pd.concat([df.iloc[:i+1], sub_df, df.iloc[i+1:]]).reset_index(drop=True)

                        i += nb_row_to_add
                    i += 1

            # add sec (60), min (60), hour (24) and day_of_week (7) features
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df["sec"] = df["time"].dt.second
            df["min"] = df["time"].dt.minute
            df["hour"] = df["time"].dt.hour
            df["day"] = df["time"].dt.dayofweek

            # remove too short flights
            if (len(df) < CTX["HISTORY"]):
                print(df["callsign"][0], df["icao24"][0], "is too short")
                continue
            

            # Get the aircraft label for his imatriculation
            icao24 = df["icao24"].iloc[0]
            label = labels[labels["icao24"] == icao24]["label"]
            
            # if no label found, skip the flight
            if (len(label) == 0):
                print("!!! no label for", icao24)
                print(df)
                continue

            label = label.iloc[0]

            # If flight label is not a filtered class, skip the flight
            if (label not in CTX["LABEL_FILTER"]):
                continue

            # Remove interpolated rows (to test the impact of not using interpolation)
            # remplace them by full row of NaN
            # rows = df[df["interpolated"] == True].index
            # df.loc[rows] = np.nan

            # Remove useless columns
            df = df[CTX["USED_FEATURES"]]

        
            # Cast booleans into numeric
            for col in df.columns:
                if (df[col].dtype == bool):
                    df[col] = df[col].astype(int)
                
            # Fill NaN with -1
            df = df.fillna(-1)
            df = df.to_numpy().astype(np.float32)

            # Add the flight to the dataset
            x.append(df)
            y.append(label)
            if (files is not None):
                files.append(file)


            done_20 = int(f/len(data_files)*20)
            print("\r|"+done_20*"="+(20-done_20)*" "+f"| {f}/{len(data_files)}", end=" "*20)
        print("\n")
        return x, y


    def __init__(self, CTX, path) -> None:    
        self.CTX = CTX
        self.x, self.y = self.__get_dataset__(path)

        # Create the scalers
        self.xScaler = MinMaxScaler3D()
        self.yScaler = SparceLabelBinarizer()



        # Fit the y scaler
        # x scaler will be fitted later after batch preprocessing
        self.y = self.yScaler.fit_transform(self.y)
        self.y = np.array(self.y, dtype=np.float32)


        # Split the dataset into train and test according to the ratio in context
        ratio = self.CTX["TEST_RATIO"]
        split_index = int(len(self.x) * (1 - ratio))
        self.x_train = self.x[:split_index]
        self.y_train = self.y[:split_index]
        self.x_test = self.x[split_index:]
        self.y_test = self.y[split_index:]




    def genEpochTrain(self, nb_batch, batch_size):
        """
        Generate the x and y input, directly usable by the model.
        Pick randoms flights from train sub-dataset, and takes a
        somes fragements of the same flight in a defined area to compose a batch.

        Called between each epoch by the trainer
        """

        # Allocate memory for the batches
        x_batches = np.zeros((nb_batch * batch_size, self.CTX["TIMESTEPS"],self.CTX["FEATURES_IN"]))
        y_batches = np.zeros((nb_batch * batch_size, self.yScaler.classes_.shape[0]))

        label_i = -1
        time_step = -1
        length = -1
        flight_i = -1

        for n in range(len(x_batches)):

            # If no label is selected, pick a random one
            # Pick a randon label to have a balanced dataset
            if (label_i == -1):
                label_i = np.random.randint(0, self.yScaler.classes_.shape[0])

                # Find a flight with this label
                flight_i = -1
                while flight_i == -1 or self.y_train[flight_i, label_i] != 1:
                    flight_i = np.random.randint(0, len(self.x_train))

                # Pick a random fragment of this flight
                time_step = np.random.randint(-self.CTX["HISTORY"]+1, len(self.x_train[flight_i]) - self.CTX["HISTORY"] - self.CTX["TRAIN_WINDOW"] * self.CTX["STEP"])
                length = 0


            # Get the fragment and paste it in the batch
            start = max(0, time_step)
            end = time_step + self.CTX["HISTORY"]

            # pad = np.zeros(((self.CTX["HISTORY"] - (end - start))//self.CTX["DILATION_RATE"], self.CTX["FEATURES_IN"]))
            pad = np.full(((self.CTX["HISTORY"] - (end - start))//self.CTX["DILATION_RATE"], self.CTX["FEATURES_IN"]), self.x_train[flight_i][start])

            x_batches[n, :, :] = np.concatenate([
                pad,
                self.x_train[flight_i][start:end:self.CTX["DILATION_RATE"]]
            ])
            y_batches[n, :] = self.y_train[flight_i]

            # If the fragment is finished, pick a new one
            # Else, get the next fragment timestep
            length += 1
            time_step += self.CTX["STEP"]
            if (length >= self.CTX["TRAIN_WINDOW"]):
                label_i = -1
                time_step = -1
                length = -1
                flight_i = -1

        # Shuffle the data
        shuffle = np.arange(len(x_batches))
        np.random.shuffle(shuffle)
        x_batches = x_batches[shuffle]
        y_batches = y_batches[shuffle]



        # Preprocess each batch
        x_batches = np.array([batchPreProcess(self.CTX, x) for x in x_batches])
        if not(self.xScaler.isFitted()):
            self.xScaler.fit(x_batches)
        x_batches = self.xScaler.transform(x_batches)

        for i in range(len(x_batches)):
            x_batches[i], y_batches[i] = add_noise(x_batches[i], y_batches[i], self.CTX["TRAINING_NOISE"])


        # Reshape the data into [nb_batch, batch_size, timestep, features]
        x_batches = x_batches.reshape(nb_batch, batch_size, self.CTX["TIMESTEPS"],  self.CTX["FEATURES_IN"])
        y_batches = y_batches.reshape(nb_batch, batch_size, self.yScaler.classes_.shape[0])


        # Check if there is any remaining nan in the data
        # wich can destroy the model gradient
        if (np.isnan(x_batches).any()):
            print("x_batches contains nan")
            exit(1)
        if (np.isnan(y_batches).any()):
            print("y_batches contains nan")
            exit(1)

        return x_batches, y_batches


    def genEpochTest(self):
        """
        Generate the x and y test.
        Pick randoms flights from train sub-dataset, and takes a
        somes fragements of it to compose batches

        Called at the end of each epoch by the trainer

        Returns:
        -------

        x_batches, y_batches: np.array
        """

        # Allocate memory for the batches (keep test ratio)
        nb_batch = int(self.CTX["BATCH_SIZE"] * self.CTX["NB_BATCH"] * self.CTX["TEST_RATIO"])
        x_batches = np.zeros((nb_batch, self.CTX["TIMESTEPS"],self.CTX["FEATURES_IN"]))
        y_batches = np.zeros((nb_batch, self.yScaler.classes_.shape[0]))

        
        for n in range(nb_batch):

            # Pick a randon label to have a balanced dataset
            label_i = np.random.randint(0, self.yScaler.classes_.shape[0])


            # Find a flight with this label
            flight_i = -1
            while flight_i == -1 or self.y_test[flight_i, label_i] != 1:
                flight_i = np.random.randint(0, len(self.x_test))

            # Pick a random fragment of this flight
            t = np.random.randint(0, len(self.x_test[flight_i]) - self.CTX["HISTORY"])

            x_batches[n, :, :] = self.x_test[flight_i][t:t+self.CTX["HISTORY"]:self.CTX["DILATION_RATE"]]
            y_batches[n, :] = self.y_test[flight_i]

            
        # Preprocess each batch
        x_batches = np.array([batchPreProcess(self.CTX, x) for x in x_batches])
        x_batches = self.xScaler.transform(x_batches)


        return x_batches, y_batches
    

    def genEval(self, path):
        """
        Load evaluation flights in the folder of desired path.
        Preprocess them same way as training flights, keep the full
        sliding window along the whole flight, and finally
        it keep a trace of the orriginal flight associated with each
        fragment of sliding window to be able to compute the accuracy
        and the final label for the complete flight

        Called at the end of each training by the trainer


        Parameters:
        ----------

        path : str
            Path to the folder containing the evaluation flights

        Returns:
        -------
        x : np.array
            Inputs data for the model

        y : np.array
            True labels associated with x batches

        associated_files : list
            List of the associated files for each fragment of sliding window
        """

        # Load all the evaluation flights and apply global preprocess to them
        associated_files = []
        x, y = self.__load_dataset__(self.CTX, path, associated_files)

        y = self.yScaler.transform(y)

        # Allocate memory for the batches
        associated_files_batches = []
        x_batches = np.zeros((0, self.CTX["TIMESTEPS"], self.CTX["FEATURES_IN"]))
        y_batches = np.zeros((0, len(self.yScaler.classes_)))

        # Create the sliding window for each flight
        for f in range(len(associated_files)):
            file = associated_files[f]



            # Create array of windows fragments 
            file_x = np.zeros((0, self.CTX["TIMESTEPS"], self.CTX["FEATURES_IN"]))

            # Pad the begining of the flight with zeros to have a prediction for the first timestep with the first window
            x[f] = np.concatenate([
                # np.zeros((self.CTX["HISTORY"] - 1, self.CTX["FEATURES_IN"])), 
                np.full((self.CTX["HISTORY"] - 1, self.CTX["FEATURES_IN"]), x[f][0]),
                 x[f]], axis=0)

            # Add each fragement
            shift = (self.CTX["DILATION_RATE"]-1)
            for t in range(self.CTX["HISTORY"], len(x[f])+1):
                file_x = np.concatenate((file_x, [x[f][t-self.CTX["HISTORY"]+shift:t:self.CTX["DILATION_RATE"]]]), axis=0)
            

            # Create the associated labels
            file_y = np.full((len(file_x), len(self.yScaler.classes_)), y[f])

            # Associate the right file name to each fragment
            associated_files_batches += [file] * len(file_x)
            x_batches = np.concatenate((x_batches, file_x), axis=0)
            y_batches = np.concatenate((y_batches, file_y), axis=0)


        # Preprocess each batch and scale them
        x_batches = np.array([batchPreProcess(self.CTX, f) for f in x_batches])
        x_batches = self.xScaler.transform(x_batches)
        y_batches = np.array(y_batches, dtype=np.float32)

        return x_batches, y_batches, associated_files_batches
