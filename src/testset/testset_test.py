import os
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.testset import TestsetGenerator
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
# Make sure your OPENAI_API_KEY is set in your environment variables or a .env file
DOCUMENT_FILE = "data/cs-handbook-gemini-cleaned.md"
OUTPUT_FILE = "data/output/ucl_cs_handbook_testset_openai.csv"
TEST_SIZE = 10

def main():
    """
    Main function to load documents, generate a test set using OpenAI models, and save it.
    """
    print("Starting the test set generation process with OpenAI models...")

    # Check for OpenAI API key
    if "OPENAI_API_KEY" not in os.environ:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set. "
            "Please create a .env file and add the key, or set it in your system's environment."
        )

    # 1. Load the document
    # We use UnstructuredMarkdownLoader to load the content of the student handbook.
    print(f"Loading document: {DOCUMENT_FILE}")
    if not os.path.exists(DOCUMENT_FILE):
        raise FileNotFoundError(f"Document not found at: {DOCUMENT_FILE}")
    loader = UnstructuredMarkdownLoader(DOCUMENT_FILE)
    documents = loader.load()

    # 2. Split the document into smaller chunks
    # A large document needs to be split into smaller chunks to be processed effectively.
    # We use RecursiveCharacterTextSplitter which is good for maintaining text continuity.
    print("Splitting document into manageable chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # The size of each chunk in characters
        chunk_overlap=200,  # The overlap between consecutive chunks
    )
    doc_chunks = text_splitter.split_documents(documents)
    print(f"Document split into {len(doc_chunks)} chunks.")

    # 3. Initialize the OpenAI Language Model and Embeddings
    # The TestsetGenerator uses a single LLM for its operations. We'll use a powerful model
    # like gpt-4o to ensure high-quality question generation.
    print("Initializing OpenAI language models...")
    llm = ChatOpenAI(model="gpt-4o")

    # We use OpenAI's latest text-embedding model for semantic understanding.
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # 4. Initialize the Ragas TestsetGenerator
    # The from_langchain class method is used to wrap Langchain models for use with Ragas.
    print("Initializing Ragas TestsetGenerator...")
    generator = TestsetGenerator.from_langchain(
        llm=llm,
        embedding_model=embeddings,
    )

    # 5. Generate the test set
    # The new Ragas API simplifies test set generation. The distributions of question types
    # are now handled internally by the generator to create a balanced test set.
    print(f"Generating a test set of {TEST_SIZE} questions. This may take some time and will incur OpenAI API costs...")
    testset = generator.generate_with_langchain_docs(
        documents=doc_chunks,
        testset_size=TEST_SIZE,
    )
    print("Test set generation complete.")

    # 6. Save the generated test set to a CSV file
    # Converting to a pandas DataFrame and saving as a CSV makes it easy to inspect and use for evaluation.
    print(f"Saving test set to {OUTPUT_FILE}...")
    df = testset.to_pandas()
    df.to_csv(OUTPUT_FILE, index=False)
    print("Test set saved successfully.")
    print("\n--- Process Finished ---")
    print(f"You can now find your high-quality test set in the file: {OUTPUT_FILE}")
    print("Sample of the generated data:")
    print(df.head())


if __name__ == "__main__":
    main()







# import os
# from langchain_community.document_loaders import UnstructuredMarkdownLoader
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# from ragas.testset import TestsetGenerator
# from dotenv import load_dotenv

# # Load environment variables from a .env file
# load_dotenv()

# # --- Configuration ---
# # Make sure your OPENAI_API_KEY is set in your environment variables or a .env file
# DOCUMENT_FILE = "data/cs-handbook-gemini-cleaned.md"
# OUTPUT_FILE = "data/output/ucl_cs_handbook_testset_openai.csv"
# TEST_SIZE = 10

# def main():
#     """
#     Main function to load documents, generate a test set using OpenAI models, and save it.
#     """
#     print("Starting the test set generation process with OpenAI models...")

#     # Check for OpenAI API key
#     if "OPENAI_API_KEY" not in os.environ:
#         raise ValueError(
#             "OPENAI_API_KEY environment variable not set. "
#             "Please create a .env file and add the key, or set it in your system's environment."
#         )

#     # 1. Load the document
#     # We use UnstructuredMarkdownLoader to load the content of the student handbook.
#     print(f"Loading document: {DOCUMENT_FILE}")
#     if not os.path.exists(DOCUMENT_FILE):
#         raise FileNotFoundError(f"Document not found at: {DOCUMENT_FILE}")
#     loader = UnstructuredMarkdownLoader(DOCUMENT_FILE)
#     documents = loader.load()

#     # 2. Split the document into smaller chunks
#     # A large document needs to be split into smaller chunks to be processed effectively.
#     # We use RecursiveCharacterTextSplitter which is good for maintaining text continuity.
#     print("Splitting document into manageable chunks...")
#     text_splitter = RecursiveCharacterTextSplitter(
#         chunk_size=1000,  # The size of each chunk in characters
#         chunk_overlap=200,  # The overlap between consecutive chunks
#     )
#     doc_chunks = text_splitter.split_documents(documents)
#     print(f"Document split into {len(doc_chunks)} chunks.")

#     # 3. Initialize the OpenAI Language Models (Generator and Critic) and Embeddings
#     # Ragas uses a generator LLM to create questions and a critic LLM to refine them.
#     print("Initializing OpenAI language models...")

#     # Using a powerful model like gpt-4o for generation and a faster model like gpt-3.5-turbo
#     # for criticism is a cost-effective approach that yields high-quality results.
#     generator_llm = ChatOpenAI(model="gpt-4o")
#     critic_llm = ChatOpenAI(model="gpt-3.5-turbo")

#     # We use OpenAI's latest text-embedding model for semantic understanding.
#     embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

#     # 4. Initialize the Ragas TestsetGenerator
#     # We configure the generator with our OpenAI models and embeddings.
#     print("Initializing Ragas TestsetGenerator...")
#     generator = TestsetGenerator.from_langchain(
#         generator_llm=generator_llm,
#         critic_llm=critic_llm,
#         embeddings=embeddings,
#     )

#     # 5. Generate the test set
#     # The new Ragas API simplifies test set generation. The distributions of question types
#     # are now handled internally by the generator to create a balanced test set.
#     print(f"Generating a test set of {TEST_SIZE} questions. This may take some time and will incur OpenAI API costs...")
#     testset = generator.generate_with_langchain_docs(
#         doc_chunks,
#         test_size=TEST_SIZE,
#     )
#     print("Test set generation complete.")

#     # 6. Save the generated test set to a CSV file
#     # Converting to a pandas DataFrame and saving as a CSV makes it easy to inspect and use for evaluation.
#     print(f"Saving test set to {OUTPUT_FILE}...")
#     df = testset.to_pandas()
#     df.to_csv(OUTPUT_FILE, index=False)
#     print("Test set saved successfully.")
#     print("\n--- Process Finished ---")
#     print(f"You can now find your high-quality test set in the file: {OUTPUT_FILE}")
#     print("Sample of the generated data:")
#     print(df.head())


# if __name__ == "__main__":
#     main()
