import openai
import streamlit as st
from utils import SemanticScholarReader
import os
from llama_index import ServiceContext, VectorStoreIndex
from llama_index import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    ServiceContext,
)
from llama_index.llms import OpenAI
import logging
from llama_index.memory import ChatMemoryBuffer
from llama_index.query_engine import CitationQueryEngine
from llama_index.embeddings import OpenAIEmbedding
import sys
from llama_index.evaluation import DatasetGenerator, QueryResponseEvaluator
from llama_index import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    ServiceContext,
    LLMPredictor,
    Response,
)
import pickle
import random

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


def create_index(research_space, num_papers, full_text):
    service_context = ServiceContext.from_defaults(
        llm=OpenAI(model="gpt-3.5-turbo", temperature=0),
        embed_model=OpenAIEmbedding(embed_batch_size=10),
    )
    # instantiating SemanticScholarReader
    s2_reader = SemanticScholarReader()
    path_to_store = (
        "./citation_" + research_space.replace(" ", "_") + "_" + str(num_papers)+ "_full_text_" + str(full_text)
    )
    # loading the data from Semantic Scholar
    if not os.path.exists(path_to_store):
        logging.info(
            "Creating index for research space: "
            + research_space
            + " with "
            + str(num_papers)
            + "papers at: "
            + path_to_store
        )
        documents = s2_reader.load_data(research_space, limit=num_papers, full_text=full_text)
        try:
            index = VectorStoreIndex.from_documents(
                documents, service_context=service_context
            )
        except Exception as e:
            logging.info("Error creating index: " + str(e))
            documents = s2_reader.load_data(research_space, limit=50)
            index = VectorStoreIndex.from_documents(
                documents, service_context=service_context
            )
        index.storage_context.persist(persist_dir=path_to_store)
        # dump documents to pickle file
        with open(path_to_store + "/documents.pkl", "wb") as f:
            pickle.dump(documents, f)
    else:
        logging.info(
            "Loading index for research space from existing index: " + path_to_store
        )
        index = load_index_from_storage(
            StorageContext.from_defaults(persist_dir=path_to_store),
            service_context=service_context,
        )
        # load documents from pickle file
        with open(path_to_store + "/documents.pkl", "rb") as f:
            documents = pickle.load(f)
        logging.info("Done loading index")

    return index, documents


def generate_sample_questions(doc_papers):
    paper = random.sample(doc_papers, 1)
    data_generator = DatasetGenerator.from_documents(paper)
    eval_questions = data_generator.generate_questions_from_nodes(3)
    return eval_questions


def prompt_for_chat(research_space):
    _prompt = (
        "You are a chatbot, able to have normal interactions, as well as talk about papers from"
        + research_space
        + ". Use your memory and make sure to cite the source of your knowledge."
    )
    return _prompt


def get_chat_engine(index, research_space):
    memory = ChatMemoryBuffer.from_defaults(token_limit=2000)
    chat_engine = index.as_chat_engine(
        chat_mode="context",
        memory=memory,
        system_prompt=prompt_for_chat(research_space),
    )
    return chat_engine


def citation_query_engine(index, k, streaming, citation_chunk_size):
    logging.info("Done creating index, loading chat . . ")
    chat_engine = CitationQueryEngine.from_args(
        index,
        similarity_top_k=k,
        streaming=streaming,
        # here we can control how granular citation sources are, the default is 512
        citation_chunk_size=citation_chunk_size,
    )
    logging.info("Done loading chat engine")
    return chat_engine
