import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter
import z3
from pytorchtreelstm.treelstm import TreeLSTM, calculate_evaluation_orders
import utils.utils as Du
from utils.Dataset import DataObj
from settings import MODEL_PATH, new_model_path
from model import Model
import json
import os
from sklearn.metrics import confusion_matrix, accuracy_score
from termcolor import colored
import argparse
import random

def evaluate(model, testset, examples_idx = None, writer = None, n = None ):
    last_batch = False

    all_true_labels = []
    all_preds  = []
    all_values = []

    while not last_batch:
        test, last_batch = dataObj.next_batch(testset, "test")
        output = model(
            test["C_batch"],
            test["L_a_batch"],
            test["L_b_batch"]
        )
        true_label = test["label_batch"].cpu()
        m = nn.Softmax(dim = 1)

        values, pred = torch.max(m(output), 1)

        all_true_labels.extend(true_label.tolist())
        all_preds.extend(pred.tolist())
        all_values.extend(values.tolist())

    acc = accuracy_score(all_true_labels, all_preds)
    print(confusion_matrix(all_true_labels, all_preds)) 
    print("accurarcy", acc)

    true_label = true_label.tolist()
    values = values.tolist()
    pred = pred.tolist()
    if examples_idx is not None:
        #grab the random 20 examples
        examples_dps = [testset[i] for i in examples_idx]
        test, last_batch = dataObj.next_batch(examples_dps, "examples")
        output = model(
            test["C_batch"],
            test["L_a_batch"],
            test["L_b_batch"]
        )
        true_label = test["label_batch"].cpu()
        m = nn.Softmax(dim = 1)

        values, pred = torch.max(m(output), 1)

        true_label = true_label.tolist()
        pred = pred.tolist()
        values = values.tolist()

        for idx in range(len(examples_dps)):
            example = examples_dps[idx]
            display_text = Du.display_example(example, true_label[idx], pred[idx], values[idx])
            
            writer.add_text('example', display_text, n)
    return acc
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-input', help='path to the ind_gen_files folder')
    parser.add_argument("-l", "--log", dest="logLevel", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='CRITICAL', help="Set the logging level")
    parser.add_argument('-v', '--vis', action='store_true')
    parser.add_argument('-C', '--use_c', action='store_true')
    parser.add_argument('-D', '--use_dot_product', action='store_true')
    parser.add_argument('-E', '--use_const_emb', action='store_true')
    parser.add_argument('-M', '--max_size', type = int, default = -1)
    parser.add_argument('-S', '--shuffle', action='store_true')
    parser.add_argument('-N', '--epoch', type = int, default = 100)
    parser.add_argument('--eval-epoch', type = int, default = 10)
    parser.add_argument('--save-epoch', type = int, default = 100)
    args = parser.parse_args()

    exp_folder = args.input
    vis = args.vis
    use_c = args.use_c
    use_const_emb = args.use_const_emb
    use_dot_product = args.use_dot_product
    max_size = args.max_size
    shuffle = args.shuffle
    n_epoch = args.epoch
    eval_epoch = args.eval_epoch
    save_epoch = args.save_epoch

    exp_name = Du.get_exp_name(exp_folder, vis, use_c, use_const_emb, use_dot_product, max_size, shuffle)
    SWRITER = SummaryWriter(comment = exp_name)
    #NOTE: batch_size should not be a divisor of the number of dps in train set or test set (batch_size = 32 while train has 4000 is not good)
    dataObj = DataObj(exp_folder, max_size = max_size, shuffle = shuffle, train_size = 0.8, batch_size = 1024)
    vocab = dataObj.vocab
    device = torch.device('cuda')
    print("DATASET SIZE:", dataObj.size())
    print("TRAIN SIZE:", dataObj.train["size"])
    print("TEST SIZE:", dataObj.test["size"])
    model = Model(vocab['size'],
                  vocab['sort_size'],
                  emb_dim = 30, #30 is the max emb_dim possible, due to the legacy dataset
                  tree_dim = 100,
                  out_dim =2,
                  use_c = use_c,
                  use_const_emb = use_const_emb,
                  use_dot_product = use_dot_product,
                  device = device).train()
    loss_function = torch.nn.CrossEntropyLoss().to(device)
    optimizer = torch.optim.Adam(model.parameters())

    metadata = {"dataset": dataObj.metadata(), "model": model.metadata()}
    SWRITER.add_text('metadata', json.dumps(metadata, indent = 2)  )
    examples_idx = random.sample(list(range(len(dataObj.test_dps))), 20)
    for n in range(n_epoch):
        last_batch = False
        total_loss = 0

        while not last_batch:
            optimizer.zero_grad()
            loss = 0
            train, last_batch = dataObj.next_batch(dataObj.train_dps, "train")
            # print("Training with %d datapoints"%train["size"])
            output = model(
                train["C_batch"],
                train["L_a_batch"],
                train["L_b_batch"]
            )
            loss = loss_function(output, train["label_batch"].to(device))
            total_loss += loss

            loss.backward()
            optimizer.step()

        # torch.cuda.empty_cache()

        if n%eval_epoch==0:
            # print(output.shape)
            train_accuracy = evaluate(model, dataObj.train_dps)
            print("example_ids:", examples_idx)
            test_accuracy = evaluate(model, dataObj.test_dps, examples_idx, SWRITER, n)
            SWRITER.add_scalar('Loss/train', total_loss, n)
            SWRITER.add_scalar('Accuracy/train', train_accuracy, n)
            SWRITER.add_scalar('Accuracy/test', test_accuracy, n)
            print(f'Iteration {n+1} Loss: {loss}')
            #check that embedding is being trained
            print(model.emb(torch.LongTensor([5]).to(device = device ) ) )

        if n%save_epoch==0:
            model_path = new_model_path(basename = exp_name)
            print("Saving to ", model_path)
            torch.save({
                'epoch': n,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'loss': loss,
                'dataset': dataObj.metadata(),
                'metadata': model.metadata()
            }, model_path)
