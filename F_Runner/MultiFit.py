



# Mlflow logging
import _Utils.mlflow as mlflow

# Convert CTX to dict for logging hyperparameters
from _Utils.module import module_to_dict 

# For auto-completion, we use Abstract class as virtual type
from B_Model.AbstractModel import Model as _Model_
from E_Trainer.AbstractTrainer import Trainer as _Trainer_


def multi_fit(Model:"type[_Model_]", Trainer:"type[_Trainer_]", CTX, iteration=3, experiment_name:str = None):
    """
    Fit the model multiple time with the given CTX of hyperparameters
    to check the stability of the model

    Parameters:
    -----------
    model: type[Model]:
        Model class type of the model to train

    trainer: type[Trainer]
        Trainer class type of the trainer algorithm to use

    CTX: Module 
        Python module containing the hyperparameters and constants

    iteration: int
        Number of time to fit the model

    experiment_name: str 
        Name of the experiment to log to mlflow
    """

    
    # Init mlflow
    run_number = mlflow.init_ml_flow(experiment_name)
    run_name = str(run_number) + " - " + Model.name

    # Convert CTX to dict and log it
    CTX = module_to_dict(CTX)
    with mlflow.start_run(run_name=run_name) as run:
        for param in CTX:
            if (type(CTX[param]) == bool): # Convert bool to int the make boolean hyperparameters visualisable in mlflow
                mlflow.log_param(param, int(CTX[param]))
            else:
                mlflow.log_param(param, CTX[param])

        
        for i in range(iteration):
            print("#############################")
            print("START Iteration", i+1, "/", iteration)
            print("#############################")
            # Instanciate the trainer and go !
            trainer = Trainer(CTX, Model)
            metrics = trainer.run()

            # Log the result metrics to mlflow
            for metric_label in metrics:
                value = metrics[metric_label]
                mlflow.log_metric(metric_label, value)

