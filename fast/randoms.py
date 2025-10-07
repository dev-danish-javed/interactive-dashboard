def understand_chunks():
    text = ","
    array = []
    for i in range(1,100):
        array.append(str(i))
    text = text.join(array, )
    print(text)

    from langchain.text_splitter import RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=10,   # you can tune this
        chunk_overlap=4, # slight overlap helps retain context
    )

    chunks = text_splitter.split_text(text)

    for chunk in chunks:
        print(chunk)

def embeddings():
    from google import genai
    import os
    from dotenv import load_dotenv
    load_dotenv()

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents="What is the meaning of life?")

    print(result.embeddings)

for i in range(1,10):
    embeddings()