import sklearn.preprocessing
from Utils import utils, base
from data.electricity import ElectricityFormatter

GenericDataFormatter = ElectricityFormatter
DataTypes = base.DataTypes
InputTypes = base.InputTypes


class CovidFormatter(GenericDataFormatter):

    _column_definition = [
        ('id', DataTypes.REAL_VALUED, InputTypes.ID),
        ('days_from_start', DataTypes.REAL_VALUED, InputTypes.TIME),
        ('PEOPLE_POSITIVE_NEW_CASES_COUNT', DataTypes.REAL_VALUED, InputTypes.TARGET),
        ('PEOPLE_POSITIVE_CASES_COUNT', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('PEOPLE_DEATH_COUNT', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('Number of Trips', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('Population Staying at Home', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('Population Not Staying at Home', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('day_of_week', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
        ('days_from_start', DataTypes.REAL_VALUED, InputTypes.KNOWN_INPUT),
    ]

    def split_data(self, df, valid_boundary=300, test_boundary=500):
        """Splits data_set frame into training-validation-test data_set frames.
        This also calibrates scaling object, and transforms data_set for each split.
        Args:
          df: Source data_set frame to split.
          valid_boundary: Starting year for validation data_set
          test_boundary: Starting year for test data_set
        Returns:
          Tuple of transformed (train, valid, test) data_set.
        """

        print('Formatting train-valid-test splits.')

        index = df['days_from_start']
        train = df.loc[index < valid_boundary]
        valid = df.loc[(index >= valid_boundary) & (index < test_boundary)]
        test = df.loc[index >= test_boundary]

        return train, valid, test

    # Default params
    def get_fixed_params(self):
        """Returns fixed model parameters for experiments."""

        fixed_params = {
            'total_time_steps': 4 * 24 + self.pred_len,
            'num_decoder_steps': self.pred_len,
            'num_epochs': 50,
            'early_stopping_patience': 5,
            'multiprocessing_workers': 5
        }

        return fixed_params

    def get_default_model_params(self):
        """Returns default optimised model parameters."""

        model_params = {
            'hidden_layer_size': [32, 64],
            'minibatch_size': [256],
            'num_heads': 8,
            'stack_size': [1],
            'context_lengths': [1, 3, 6, 9]
        }

        return model_params

    def get_num_samples_for_calibration(self):
        """Gets the default number of training and validation samples.
        Use to sub-sample the data_set for network calibration and a value of -1 uses
        all available samples.
        Returns:
          Tuple of (training samples, validation samples)
        """
        return 64000, 6400