import argparse
import json
import random

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import os

from Utils.base_train import batching, ModelData, batch_sampled_data
from data.data_loader import ExperimentConfig
from models.eff_acat import Transformer

parser = argparse.ArgumentParser(description="preprocess argument parser")
parser.add_argument("--attn_type", type=str, default='basic_attn')
parser.add_argument("--name", type=str, default='basic_attn')
parser.add_argument("--exp_name", type=str, default='covid')
parser.add_argument("--cuda", type=str, default="cuda:0")
parser.add_argument("--pred_len", type=int, default=24)

args = parser.parse_args()

kernel = [1, 3, 6, 9]
n_heads = 8
d_model = [16, 32]
batch_size = 256

config = ExperimentConfig(args.pred_len, args.exp_name)

formatter = config.make_data_formatter()
params = formatter.get_experiment_params()
total_time_steps = params['total_time_steps']
num_encoder_steps = params['num_encoder_steps']
column_definition = params["column_definition"]
pred_len = args.pred_len

device = torch.device(args.cuda if torch.cuda.is_available() else "cpu")
data_csv_path = "{}.csv".format(args.exp_name)
raw_data = pd.read_csv(data_csv_path)

data = formatter.transform_data(raw_data)
train_max, valid_max = formatter.get_num_samples_for_calibration()
max_samples = (train_max, valid_max)

train, valid, test = batch_sampled_data(data, 0.8, max_samples, params['total_time_steps'],
                                        params['num_encoder_steps'], pred_len,
                                        params["column_definition"],
                                        device)

test_batching = batching(batch_size, test.enc, test.dec, test.y_true, test.y_id)
test = ModelData(test_batching[0], test_batching[1], test_batching[2], test_batching[3], device)

device = torch.device(args.cuda if torch.cuda.is_available() else "cpu")
model_path = "models_{}_{}".format(args.exp_name, pred_len)
model_params = formatter.get_default_model_params()

src_input_size = test.enc.shape[3]
tgt_input_size = test.dec.shape[3]

predictions = np.zeros((3, test.y_true.shape[0], test.y_true.shape[1], test.y_true.shape[2]))
n_batches_test = test.enc.shape[0]
y_true = test.y_true.squeeze(-1).detach().cpu()

mse = nn.MSELoss()
mae = nn.L1Loss()

for i, seed in enumerate([4293, 1692, 3029]):
    try:
        for stack_size in [1, 3]:
            for d in d_model:
                for k in kernel:
                    d_k = int(d / n_heads)

                    model = Transformer(src_input_size=src_input_size,
                                        tgt_input_size=tgt_input_size,
                                        pred_len=pred_len,
                                        d_model=d,
                                        d_ff=d * 4,
                                        d_k=d_k, d_v=d_k, n_heads=n_heads,
                                        n_layers=stack_size, src_pad_index=0,
                                        tgt_pad_index=0, device=device,
                                        attn_type=args.attn_type,
                                        seed=seed, kernel=k)

                    checkpoint = torch.load(os.path.join("models_{}_{}".format(args.exp_name, args.pred_len),
                                            "{}_{}".format(args.name, seed)))
                    model.load_state_dict(checkpoint['model_state_dict'])
                    model.eval()
                    model.to(device)

                    for j in range(n_batches_test):
                        output = model(test.enc[j], test.dec[j])
                        predictions[i, j] = output.squeeze(-1).cpu().detach().numpy()

    except RuntimeError:
        pass

predictions = torch.from_numpy(np.mean(predictions, axis=0))

results = torch.zeros(2, args.pred_len)
normaliser = y_true.abs().mean()

test_loss = mse(predictions, y_true).item() / normaliser
mae_loss = mae(predictions, y_true).item() / normaliser

for j in range(args.pred_len):

    results[0, j] = mse(predictions[:, :, j], y_true[:, :, j]).item()
    results[1, j] = mae(predictions[:, :, j], y_true[:, :, j]).item()

df = pd.DataFrame(results.detach().cpu().numpy())
df.to_csv("{}_{}_{}.csv".format(args.exp_name, args.name, args.pred_len))

erros = dict()
erros["{}".format(args.name)] = list()
erros["{}".format(args.name)].append(float("{:.5f}".format(test_loss)))
erros["{}".format(args.name)].append(float("{:.5f}".format(mae_loss)))

error_path = "new_Errors_{}_{}.json".format(args.exp_name, pred_len)

if os.path.exists(error_path):
    with open(error_path) as json_file:
        json_dat = json.load(json_file)
        if json_dat.get("{}".format(args.name)) is None:
            json_dat["{}".format(args.name)] = list()
        json_dat["{}".format(args.name)].append(float("{:.5f}".format(test_loss)))
        json_dat["{}".format(args.name)].append(float("{:.5f}".format(mae_loss)))

    with open(error_path, "w") as json_file:
        json.dump(json_dat, json_file)
else:
    with open(error_path, "w") as json_file:
        json.dump(erros, json_file)
