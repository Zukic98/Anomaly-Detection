

# Import the model
from B_Model.TrajectorySeparator.Model import Model

# Import the context (hyperparameters, constants, etc...)
import C_Constants.TrajectorySeparator.Model as CTX
import C_Constants.TrajectorySeparator.DefaultCTX as DefaultCTX

# Import the training loop adapted to the model
from E_Trainer.TrajectorySeparator.Trainer import Trainer

# Choose the training method
from F_Runner.FitOnce import *
from F_Runner.MultiFit import *

import os


def __main__():
    parent_dir = os.path.dirname(os.path.abspath(__file__)).split("/")[-1]
    fitOnce(Model, Trainer, CTX, default_CTX=DefaultCTX, experiment_name=parent_dir)

