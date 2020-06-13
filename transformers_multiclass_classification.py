# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %% [markdown]
# # Fine Tuning Transformer for MultiClass Text Classification
# %% [markdown]
# ### Introduction
# 
# In this tutorial we will be fine tuning a transformer model for the **Multiclass text classification** problem. 
# This is one of the most common business problems where a given piece of text/sentence/document needs to be classified into one of the categories out of the given list.
# 
# #### Flow of the notebook
# 
# The notebook will be divided into seperate sections to provide a organized walk through for the process used. This process can be modified for individual use cases. The sections are:
# 
# 1. [Importing Python Libraries and preparing the environment](#section01)
# 2. [Importing and Pre-Processing the domain data](#section02)
# 3. [Preparing the Dataset and Dataloader](#section03)
# 4. [Creating the Neural Network for Fine Tuning](#section04)
# 5. [Fine Tuning the Model](#section05)
# 6. [Validating the Model Performance](#section06)
# 7. [Saving the model and artifacts for Inference in Future](#section07)
# 
# #### Technical Details
# 
# This script leverages on multiple tools designed by other teams. Details of the tools used below. Please ensure that these elements are present in your setup to successfully implement this script.
# 
#  - Data: 
# 	 - We are using the News aggregator dataset available at by [UCI Machine Learning Repository](https://archive.ics.uci.edu/ml/datasets/News+Aggregator)
# 	 - We are referring only to the first csv file from the data dump: `newsCorpora.csv`
# 	 - There are `422937` rows of data.  Where each row has the following data-point: 
# 		 - ID Numeric ID  
# 		 - TITLE News title  
# 		 - URL Url  
# 		 - PUBLISHER Publisher name  
# 		 - CATEGORY News category (b = business, t = science and technology, e = entertainment, m = health)  
# 		 - STORY Alphanumeric ID of the cluster that includes news about the same story  
# 		 - HOSTNAME Url hostname  
# 		 - TIMESTAMP Approximate time the news was published, as the number of milliseconds since the epoch 00:00:00 GMT, January 1, 1970
# 
# 
#  - Language Model Used:
# 	 - DistilBERT this is a smaller transformer model as compared to BERT or Roberta. It is created by process of distillation applied to Bert. 
# 	 - [Blog-Post](https://medium.com/huggingface/distilbert-8cf3380435b5)
# 	 - [Research Paper](https://arxiv.org/abs/1910.01108)
#      - [Documentation for python](https://huggingface.co/transformers/model_doc/distilbert.html)
# 
# 
#  - Hardware Requirements:
# 	 - Python 3.6 and above
# 	 - Pytorch, Transformers and All the stock Python ML Libraries
# 	 - GPU enabled setup 
# 
# 
#  - Script Objective:
# 	 - The objective of this script is to fine tune DistilBERT to be able to classify a news headline into the following categories:
# 		 - Business
# 		 - Technology
# 		 - Health
# 		 - Entertainment 
# 
# %% [markdown]
# <a id='section01'></a>
# ### Importing Python Libraries and preparing the environment
# 
# At this step we will be importing the libraries and modules needed to run our script. Libraries are:
# * Pandas
# * Pytorch
# * Pytorch Utils for Dataset and Dataloader
# * Transformers
# * DistilBERT Model and Tokenizer
# 
# Followed by that we will preapre the device for CUDA execeution. This configuration is needed if you want to leverage on onboard GPU. 

# %%
# Importing the libraries needed
import pandas as pd
import torch
import transformers
from torch.utils.data import Dataset, DataLoader
from transformers import DistilBertModel, DistilBertTokenizer
import tqdm

# %%
# Setting up the device for GPU usage

from torch import cuda
device = 'cuda' if cuda.is_available() else 'cpu'

# %% [markdown]
# <a id='section02'></a>
# ### Importing and Pre-Processing the domain data
# 
# We will be working with the data and preparing for fine tuning purposes. 
# *Assuming that the `newCorpora.csv` is already downloaded in your `data` folder*
# 
# Import the file in a dataframe and give it the headers as per the documentation.
# Cleaning the file to remove the unwanted columns and create an additional column for training.
# The final Dataframe will be something like this:
# 
# |TITLE|CATEGORY|ENCODED_CAT|
# |--|--|--|
# |  title_1|Entertainment | 1 |
# |  title_2|Entertainment | 1 |
# |  title_3|Business| 2 |
# |  title_4|Science| 3 |
# |  title_5|Science| 3 |
# |  title_6|Health| 4 |

# %%
# Import the csv into pandas dataframe and add the headers
df = pd.read_csv('./data/newsCorpora.csv', sep='\t', names=['ID','TITLE', 'URL', 'PUBLISHER', 'CATEGORY', 'STORY', 'HOSTNAME', 'TIMESTAMP'])
# df.head()
# # Removing unwanted columns and only leaving title of news and the category which will be the target
df = df[['TITLE','CATEGORY']]
# df.head()

# # Converting the codes to appropriate categories using a dictionary
my_dict = {
    'e':'Entertainment',
    'b':'Business',
    't':'Science',
    'm':'Health'
}

def update_cat(x):
    return my_dict[x]

df['CATEGORY'] = df['CATEGORY'].apply(lambda x: update_cat(x))

encode_dict = {}

def encode_cat(x):
    if x not in encode_dict.keys():
        encode_dict[x]=len(encode_dict)
    return len(encode_dict)

df['ENCODE_CAT'] = df['CATEGORY'].apply(lambda x: encode_cat(x))

# %% [markdown]
# <a id='section03'></a>
# ### Preparing the Dataset and Dataloader
# 
# We will start with defining few key variables that will be used later during the training/fine tuning stage.
# Followed by creation of Dataset class - This defines how the text is pre-processed before sending it to the neural network. We will also define the Dataloader that will feed  the data in batches to the neural network for suitable training and processing. 
# Dataset and Dataloader are constructs of the PyTorch library for defining and controlling the data pre-processing and its passage to neural network. For further reading into Dataset and Dataloader read the [docs at PyTorch](https://pytorch.org/docs/stable/data.html)
# 
# #### *Triage* Dataset Class
# - This class is defined to accept the Dataframe as input and generate tokenized output that is used by the DistilBERT model for training. 
# - We are using the DistilBERT tokenizer to tokenize the data in the `TITLE` column of the dataframe. 
# - The tokenizer uses the `encode_plus` method to perform tokenization and generate the necessary outputs, namely: `ids`, `attention_mask`
# - To read further into the tokenizer, [refer to this document](https://huggingface.co/transformers/model_doc/distilbert.html#distilberttokenizer)
# - `target` is the encoded category on the news headline. 
# - The *Triage* class is used to create 2 datasets, for training and for validation.
# - *Training Dataset* is used to fine tune the model: **80% of the original data**
# - *Validation Dataset* is used to evaluate the performance of the model. The model has not seen this data during training. 
# 
# #### Dataloader
# - Dataloader is used to for creating training and validation dataloader that load data to the neural network in a defined manner. This is needed because all the data from the dataset cannot be loaded to the memory at once, hence the amount of dataloaded to the memory and then passed to the neural network needs to be controlled.
# - This control is achieved using the parameters such as `batch_size` and `max_len`.
# - Training and Validation dataloaders are used in the training and validation part of the flow respectively

# %%
# Defining some key variables that will be used later on in the training
MAX_LEN = 512
TRAIN_BATCH_SIZE = 4
VALID_BATCH_SIZE = 2
EPOCHS = 1
LEARNING_RATE = 1e-05
tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-cased')


# %%
class Triage(Dataset):
    def __init__(self, dataframe, tokenizer, max_len):
        self.len = len(dataframe)
        self.data = dataframe
        self.tokenizer = tokenizer
        self.max_len = max_len
        
    def __getitem__(self, index):
        title = str(self.data.TITLE[index])
        title = " ".join(title.split())
        inputs = self.tokenizer.encode_plus(
            title,
            None,
            add_special_tokens=True,
            max_length=self.max_len,
            pad_to_max_length=True,
            return_token_type_ids=True
        )
        ids = inputs['input_ids']
        mask = inputs['attention_mask']

        return {
            'ids': torch.tensor(ids, dtype=torch.long),
            'mask': torch.tensor(mask, dtype=torch.long),
            'targets': torch.tensor(self.data.ENCODE_CAT[index], dtype=torch.long)
        } 
    
    def __len__(self):
        return self.len


# %%
# Creating the dataset and dataloader for the neural network

train_size = 0.8
train_dataset=df.sample(frac=train_size,random_state=200).reset_index(drop=True)
test_dataset=df.drop(train_dataset.index).reset_index(drop=True)


print("FULL Dataset: {}".format(df.shape))
print("TRAIN Dataset: {}".format(train_dataset.shape))
print("TEST Dataset: {}".format(test_dataset.shape))

training_set = Triage(train_dataset, tokenizer, MAX_LEN)
testing_set = Triage(test_dataset, tokenizer, MAX_LEN)


# %%
train_params = {'batch_size': TRAIN_BATCH_SIZE,
                'shuffle': True,
                'num_workers': 0
                }

test_params = {'batch_size': VALID_BATCH_SIZE,
                'shuffle': True,
                'num_workers': 0
                }

training_loader = DataLoader(training_set, **train_params)
testing_loader = DataLoader(testing_set, **test_params)

# %% [markdown]
# <a id='section04'></a>
# ### Creating the Neural Network for Fine Tuning
# 
# #### Neural Network
#  - We will be creating a neural network with the `DistillBERTClass`. 
#  - This network will have the DistilBERT Language model followed by a `dropout` and finally a `Linear` layer to obtain the final outputs. 
#  - The data will be fed to the DistilBERT Language model as defined in the dataset. 
#  - Final layer outputs is what will be compared to the `encoded category` to determine the accuracy of models prediction. 
#  - We will initiate an instance of the network called `model`. This instance will be used for training and then to save the final trained model for future inference. 
#  
# #### Loss Function and Optimizer
#  - `Loss Function` and `Optimizer` and defined in the next cell.
#  - The `Loss Function` is used the calculate the difference in the output created by the model and the actual output. 
#  - `Optimizer` is used to update the weights of the neural network to improve its performance.
#  
# #### Further Reading
# - You can refer to my [Pytorch Tutorials](https://github.com/abhimishra91/pytorch-tutorials) to get an intuition of Loss Function and Optimizer.
# - [Pytorch Documentation for Loss Function](https://pytorch.org/docs/stable/nn.html#loss-functions)
# - [Pytorch Documentation for Optimizer](https://pytorch.org/docs/stable/optim.html)
# - Refer to the links provided on the top of the notebook to read more about DistiBERT. 

# %%
# Creating the customized model, by adding a drop out and a dense layer on top of distil bert to get the final output for the model. 

class DistillBERTClass(torch.nn.Module):
    def __init__(self):
        super(DistillBERTClass, self).__init__()
        self.l1 = transformers.DistilBertModel.from_pretrained('distilbert-base-uncased')
        self.l2 = torch.nn.Dropout(0.3)
        self.l3 = torch.nn.Linear(768, 1)
    
    def forward(self, ids, mask):
        output_1= self.l1(ids, mask)
        output_2 = self.l2(output_1[0])
        output = self.l3(output_2)
        return output


# %%
model = DistillBERTClass()
model.to(device)


# %%
# Creating the loss function and optimizer
loss_function = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(params =  model.parameters(), lr=LEARNING_RATE)

# %% [markdown]
# <a id='section05'></a>
# ### Fine Tuning the Model
# 
# After all the effort of loading and preparing the data and datasets, creating the model and defining its loss and optimizer. This is probably the easier steps in the process. 
# 
# Here we define a training function that trains the model on the training dataset created above, specified number of times (EPOCH), An epoch defines how many times the complete data will be passed through the network. 
# 
# Following events happen in this function to fine tune the neural network:
# - The dataloader passes data to the model based on the batch size. 
# - Subsequent output from the model and the actual category are compared to calculate the loss. 
# - Loss value is used to optimize the weights of the neurons in the network.
# - After every 5000 steps the loss value is printed in the console.
# 
# As you can see just in 1 epoch by the final step the model was working with a miniscule loss of 0.0002485 i.e. the output is extremely close to the actual output.

# %%
# Defining the training function on the 80% of the dataset for tuning the distilbert model

def train(epoch):
    model.train()
    for _,data in enumerate(tqdm.tqdm(training_loader), 0):
        ids = data['ids'].to(device, dtype = torch.long)
        mask = data['mask'].to(device, dtype = torch.long)
        targets = data['targets'].to(device, dtype = torch.long)

        outputs = model(ids, mask)
        outputs = outputs.squeeze()

        optimizer.zero_grad()
        loss = loss_function(outputs, targets)
        if _%5000==0:
            print(f'Epoch: {epoch}, Loss:  {loss.item()}')
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()


# %%
for epoch in range(EPOCHS):
    train(epoch)

# %% [markdown]
# <a id='section06'></a>
# ### Validating the Model
# 
# During the validation stage we pass the unseen data(Testing Dataset) to the model. This step determines how good the model performs on the unseen data. 
# 
# This unseen data is the 20% of `newscorpora.csv` which was seperated during the Dataset creation stage. 
# During the validation stage the weights of the model are not updated. Only the final output is compared to the actual value. This comparison is then used to calcuate the accuracy of the model. 
# 
# As you can see the model is predicting the correct category of a given headline to a 99.9% accuracy.

# %%
def valid(model, testing_loader):
    model.eval()
    n_correct = 0; n_wrong = 0; total = 0
    with torch.no_grad():
        for _, data in enumerate(testing_loader, 0):
            ids = data['ids'].to(device, dtype = torch.long)
            mask = data['mask'].to(device, dtype = torch.long)
            targets = data['targets'].to(device, dtype = torch.long)
            outputs = model(ids, mask).squeeze()
            big_val, big_idx = torch.max(outputs.data, dim=1)
            total+=targets.size(0)
            n_correct+=(big_idx==targets).sum().item()
    return (n_correct*100.0)/total


# %%
print('This is the validation section to print the accuracy and see how it performs')
print('Here we are leveraging on the dataloader crearted for the validation dataset, the approcah is using more of pytorch')

acc = valid(model, testing_loader)
print("Accuracy on test data = %0.2f%%" % acc)

# %% [markdown]
# <a id='section07'></a>
# ### Saving the Trained Model Artifacts for inference
# 
# This is the final step in the process of fine tuning the model. 
# 
# The model and its vocabulary are saved locally. These files are then used in the future to make inference on new inputs of news headlines.
# 
# Please remember that a trained neural network is only useful when used in actual inference after its training. 
# 
# In the lifecycle of an ML projects this is only half the job done. We will leave the inference of these models for some other day. 

# %%
# Saving the files for re-use

output_model_file = './models/pytorch_distilbert_news.bin'
output_vocab_file = './models/vocab_distilbert_news.bin'

model_to_save = model
torch.save(model_to_save, output_model_file)
tokenizer.save_vocabulary(output_vocab_file)

print('All files saved')
print('This tutorial is completed')

