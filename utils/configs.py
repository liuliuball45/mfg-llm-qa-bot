# Databricks notebook source
#%pip install git+https://github.com/databricks-academy/dbacademy@v1.0.13 git+https://github.com/databricks-industry-solutions/notebook-solution-companion@safe-print-html --quiet --disable-pip-version-check

# COMMAND ----------

# MAGIC %md Before setting up the rest of the accelerator, we need set up an [HuggingFace access token in order to access Open sourced models on HuggingFace](https://huggingface.co/docs/hub/security-tokens). Here we demonstrate using the [Databricks Secret Scope](https://docs.databricks.com/security/secrets/secret-scopes.html) for credential management. 
# MAGIC
# MAGIC Copy the block of code below, replace the name of the secret scope and fill in the credentials and execute the block. After executing the code, The accelerator notebook will be able to access the credentials it needs.
# MAGIC
# MAGIC
# MAGIC ```
# MAGIC from solacc.companion import NotebookSolutionCompanion
# MAGIC
# MAGIC client = NotebookSolutionCompanion().client
# MAGIC try:
# MAGIC   client.execute_post_json(f"{client.endpoint}/api/2.0/secrets/scopes/create", {"scope": "solution-accelerator-cicd"})
# MAGIC except:
# MAGIC   pass
# MAGIC   
# MAGIC client.execute_post_json(f"{client.endpoint}/api/2.0/secrets/put", {
# MAGIC   "scope": "solution-accelerator-cicd",
# MAGIC   "key": "openai_api",
# MAGIC   "string_value": '____' 
# MAGIC })
# MAGIC ```

# COMMAND ----------

import os
os.environ['HUGGINGFACEHUB_API_TOKEN'] = dbutils.secrets.get('solution-accelerator-cicd', 'huggingface')    #mfg-llm-solution-accel2 #rkm-scope
os.environ['HF_HOME'] = '/dbfs/temp/hfmfgcache'

# COMMAND ----------

import subprocess
subprocess.call('huggingface-cli login --token $HUGGINGFACEHUB_API_TOKEN', shell=True)

# COMMAND ----------

def dbfsnormalize(path):
  path = path.replace('/dbfs/', 'dbfs:/')
  return path

# COMMAND ----------

username = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()

# COMMAND ----------

configs = {}
configs.update({'vector_persist_dir' : '/dbfs/temp/faissv1'}) #/dbfs/temp/faissv1
configs.update({'data_dir':f'/dbfs/Users/{username}/data/sds_pdf'})
configs.update({'chunk_size':600})
configs.update({'chunk_overlap':20})

#configs.update({'temperature':0.8})
#configs.update({'max_new_tokens':128})
# configs.update({'prompt_template':"""Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

# {context}

# Question: {question}"""})

configs.update({'prompt_template':"""Use the following pieces of information to answer the user's question.
If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context: {context}
Question: {question}

Only return the helpful answer below and nothing else.
Helpful answer:
"""})

configs.update({'num_similar_docs':10})
configs.update({'registered_model_name':'mfg-llm-qabot'})
configs.update({'HF_key_secret_scope':'solution-accelerator-cicd'})
configs.update({'HF_key_secret_key':'huggingface'})
configs.update({'serving_endpoint_name':'mfg-llm-qabot-serving-endpoint'})


#configs.update({'model_name' : 'togethercomputer/RedPajama-INCITE-Instruct-3B-v1'})
#configs.update({'tokenizer_name' : 'togethercomputer/RedPajama-INCITE-Instruct-3B-v1'})
#configs.update({'model_name' : 'gpt2-xl'})
#configs.update({'tokenizer_name' : 'gpt2-xl'})
#configs.update({'model_name' : 'google/flan-t5-xl'})
#configs.update({'tokenizer_name' : 'google/flan-t5-xl'})
# configs.update({'model_name' : 'bigscience/bloomz-7b1'})
# configs.update({'tokenizer_name' : 'bigscience/bloomz-7b1'})
# configs.update({'model_name' : 'mosaicml/mpt-7b-instruct'})
# configs.update({'tokenizer_name' : 'EleutherAI/gpt-neox-20b'}) #for mpt
#configs.update({'model_name' : 'tiiuae/falcon-7b-instruct'})
#configs.update({'tokenizer_name' : 'tiiuae/falcon-7b-instruct'})
configs.update({'model_name' : 'meta-llama/Llama-2-7b-chat-hf'})
configs.update({'tokenizer_name' : 'meta-llama/Llama-2-7b-chat-hf'})


#torch_dtype=float16, #for gpu
#torch_dtype=bfloat16, #for cpu
#load_in_8bit=True #, #8 bit stuff needs accelerate which I couldnt get to work with model serving
#max_seq_len=1440 #rkm removed for redpajama

import torch

if 'falcon' in configs['model_name']:
  automodelconfigs = {
      'trust_remote_code':True,
      'device_map':'auto', 
      'torch_dtype':torch.float16 #torch.float16 changed to bfloat for falcon. changed back to float for falcon
      }
elif 'lama-2-' in configs['model_name']:
  automodelconfigs = {
    'trust_remote_code':True,
    'device_map':'auto', 
    #'low_cpu_mem_usage':True,
    'torch_dtype':torch.float16 #
    } 
else:
  automodelconfigs = {
      'trust_remote_code':True,
      'device_map':'auto', 
      'torch_dtype':torch.bfloat16
      }
  

if 'flan' in configs['model_name']:
  pipelineconfigs = {
      'task':'text2text-generation', #'text-generation',
      'temperature':0.8,  # 'randomness' of outputs, 0.0 is the min and 1.0 the max
      'top_p':0.80,  # select from top tokens whose probability add up to 80%
      'top_k':8,  # select from top 0 tokens (because zero, relies on top_p)
      'max_new_tokens':60,  # mex number of tokens to generate in the output
      'repetition_penalty':1.1, # without this output begins repeating
      #'return_full_text':True  # langchain expects the full text
  }
elif 'lama-2-' in configs['model_name']:
  pipelineconfigs = {
      'task':'text-generation',
      'temperature':0.8,  # 'randomness' of outputs, 0.0 is the min and 1.0 the max
      'top_p':0.80,  # select from top tokens whose probability add up to 80%
      'top_k':0,  # select from top 0 tokens (because zero, relies on top_p)
      'max_new_tokens':400,  # mex number of tokens to generate in the output
      'repetition_penalty':1.1, # without this output begins repeating
      #'max_length':128,
      'return_full_text':True  # langchain expects the full text
  }   
else:
  pipelineconfigs = {
      'task':'text-generation',
      'temperature':0.8,  # 'randomness' of outputs, 0.0 is the min and 1.0 the max
      'top_p':0.80,  # select from top tokens whose probability add up to 80%
      'top_k':0,  # select from top 0 tokens (because zero, relies on top_p)
      'max_new_tokens':128,  # mex number of tokens to generate in the output
      'repetition_penalty':1.1, # without this output begins repeating
      #'max_answer_len':100, #remove for red pajama & bloom & falcon
      'return_full_text':True  # langchain expects the full text
  }  


# COMMAND ----------

# DBTITLE 1,Databricks url and token
import os
ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
configs['databricks token'] = ctx.apiToken().getOrElse(None)
configs['databricks url'] = ctx.apiUrl().getOrElse(None)
os.environ['DATABRICKS_TOKEN'] = configs["databricks token"]
os.environ['DATABRICKS_URL'] = configs["databricks url"]

# COMMAND ----------

# DBTITLE 1,MLflow experiment
import mlflow
mlflow.set_experiment('/Users/{}/mfg_llm_sds_search'.format(username))
