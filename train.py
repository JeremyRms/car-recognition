import copy
import time

import numpy as np
import torch
from matplotlib import pyplot as plt

import config
from torch.utils.data import DataLoader, random_split
from torchvision import models, transforms

from dataset_preprocessing import VmmrdbDataset, DatasetPreprocessing
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
def create_model(num_classes):
    model = models.resnet152(weights=models.ResNet152_Weights.DEFAULT)
    # Resnet152 has a final layer with 1000 classes. We change it to the number of our own clases.
    model.fc = torch.nn.Linear(model.fc.in_features, num_classes)
    model = model.to(device)
    return model

def save_checkpoint(epoch, model_state_dict, optimizer_state_dict, epoch_loss, epoch_acc):
    torch.save({
        "epoch": epoch,
        "model_state_dict": model_state_dict,
        "optimizer_state_dict": optimizer_state_dict,
        "loss": epoch_loss,
        "accuracy": epoch_acc,
    }, "models/checkpoints/checkpoint")
    print("-------Saved Checkpoint---------\n\n")

def load_checkpoint(model, optimizer):
    checkpoint = torch.load(config.CHECKPOINT_PATH)
    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    epoch_loss = checkpoint["loss"]
    epoch_acc = checkpoint["accuracy"]
    epoch = checkpoint["epoch"]
    print(f"-------Loaded {config.CHECKPOINT_PATH} Checkpoint---------")
    return epoch, model, optimizer, epoch_loss, epoch_acc


def train_model(model, criterion, optimizer, scheduler, num_epochs, dataloaders, dataset_sizes, checkpoint=False):
    since = time.time()
    best_model_weights = copy.deepcopy(model.state_dict())
    best_accuracy = 0.0
    train_loss, val_loss = [], []

    if checkpoint:
        previously_trained_epochs, model, optimizer, _, _ = load_checkpoint(model, optimizer)
        # Complete only the rest of epochs.
        num_epochs = num_epochs - previously_trained_epochs

    for epoch in range(num_epochs):
        print(f"Epoch {epoch + 1} / {num_epochs}")
        print("-" * 10)

        # Each epoch has a training and validation phase
        for phase in ["train", "val"]:
            if phase == "train":
                model.train()
            else:
                model.eval()

            running_loss = 0.0
            running_corrects = 0

            for batch_idx, batch_data in enumerate(dataloaders[phase]):
                inputs_ = batch_data["image"].to(device)
                labels_ = batch_data["label"].to(device)

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward and trach history if only train.
                with torch.set_grad_enabled(phase == "train"):
                    outputs = model(inputs_)
                    _, preds = torch.max(outputs, dim=1)
                    loss = criterion(outputs, labels_)

                    # backward + optimize only if in training phase.
                    if phase == "train":
                        loss.backward()
                        optimizer.step()

                # statistics
                running_loss += loss.item() * inputs_.size(0)
                running_corrects += torch.sum(preds == labels_.data).item()

            if phase == "train":
                scheduler.step()

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects / dataset_sizes[phase]

            if phase == "train":
                train_loss.append(epoch_loss)
            else:
                val_loss.append(epoch_loss)

            print(f"Phase {phase} Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.4f}")

            # deep copy the model
            if phase == "val" and epoch_acc > best_accuracy:
                best_accuracy = epoch_acc
                best_model_weights = copy.deepcopy(model.state_dict())

        save_checkpoint(epoch, best_model_weights, optimizer.state_dict(), epoch_loss, epoch_acc)

    time_elapsed = time.time() - since
    print(f"Training complete in {time_elapsed // 60:.0f}, {time_elapsed % 60:.0f}s")
    print(f"Best val accuracy: {best_accuracy}")

    model.load_state_dict(best_model_weights)
    plt.plot(range(1, len(train_loss) + 1), train_loss, label="training loss")
    plt.plot(range(1, len(val_loss) + 1), val_loss, label="validation loss")
    plt.legend()
    plt.show()
    return model