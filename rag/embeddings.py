import os
from dotenv import load_dotenv
from google import genai
from sqlalchemy import create_engine, inspect

from langchain.text_splitter import RecursiveCharacterTextSplitter

load_dotenv()

engine = create_engine(os.getenv("DB_URI"))
insp = inspect(engine)

schema = {}

# Format into readable text for embeddings
def schema_to_text(schema_dict):
    text_parts = []
    for table, info in schema_dict.items():
        text_parts.append(f"Table: {table}")
        for col in info["columns"]:
            text_parts.append(
                f"  - Column '{col['name']}' ({col['type']}), "
                f"{'NULL allowed' if col['nullable'] else 'NOT NULL'}"
                + (f", default: {col['default']}" if col['default'] else "")
            )
        if info["primary_keys"]:
            text_parts.append(f"  Primary Keys: {', '.join(info['primary_keys'])}")
        text_parts.append('\n')
        for fk in info["foreign_keys"]:
            text_parts.append(
                f"  Foreign Key: {fk['column']} → {fk['referred_table']}({fk['referred_columns']})"
            )
        if info["indexes"]:
            for idx in info["indexes"]:
                text_parts.append(
                    f"  Index: {idx['name']} on {idx['columns']} "
                    f"{'(unique)' if idx['unique'] else ''}"
                )
        text_parts.append("")
    return "\n".join(text_parts)

# pull data from db
for table_name in insp.get_table_names():
    table_info = {"columns": [], "primary_keys": [], "foreign_keys": [], "indexes": []}

    # Columns info
    for col in insp.get_columns(table_name):
        table_info["columns"].append({
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col["nullable"],
            "default": col.get("default")
        })

    # Primary keys
    table_info["primary_keys"] = insp.get_pk_constraint(table_name).get("constrained_columns", [])

    # Foreign keys
    fks = insp.get_foreign_keys(table_name)
    for fk in fks:
        table_info["foreign_keys"].append({
            "column": fk["constrained_columns"],
            "referred_table": fk["referred_table"],
            "referred_columns": fk["referred_columns"]
        })

    # Indexes
    for idx in insp.get_indexes(table_name):
        table_info["indexes"].append({
            "name": idx["name"],
            "columns": idx["column_names"],
            "unique": idx.get("unique", False)
        })

    schema[table_name] = table_info

# convert schema to text
schema_str = schema_to_text(schema)

# create chunk config
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,   # you can tune this
    chunk_overlap=50, # slight overlap helps retain context
)

# create chunks
chunks = text_splitter.split_text(schema_str)

# creat gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# we'll store embeddings
embeddings = []
texts = []
# pass chunks to llm to create embedding
for chunk in chunks:
    response = client.models.embed_content(
        model="gemini-embedding-001",  # Gemini embedding model
        contents=chunk
    )
    # extract embedding from response and store
    texts.append(chunk)
    embeddings.append(response.embeddings[0].values)


import chromadb
db_client = chromadb.Client()
collection = db_client.create_collection(name="db_schema")

ids = [str(i) for i in range(len(embeddings))]

# Add embeddings to Chroma
collection.add(ids=ids, embeddings=embeddings, documents=texts)

# Take user query
user_query = input("User: ")
query_response = client.models.embed_content(
model="gemini-embedding-001",
contents=user_query,
)
query_vector = query_response.embeddings[0].values

query_results = collection.query(query_embeddings=[query_vector], n_results=4)


def execute_query(query):
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.fetchall()
    return rows


## Let's now start the chat
from openai import OpenAI
client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
chat = []

application_prompt = {"role": "system", "content": f"""You are an expert Oracle SQL assistant. The database you are working on is oracle db.
                        Use only the provided database schema to answer queries.
                        STRICT OUTPUT RULES:
                        - Output ONLY raw SQL text.
                        - Do not wrap the sql in markdown
                        - Always return a valid Oracle SQL script.
                        - Do not add a trailing semicolon.

                        Example of correct output:
                            SELECT * FROM users

                        Example of wrong output:
                            ```sql
                            SELECT * FROM users;
                            ```

                        Below is the oracle db schema :\n {query_results}
                        """}

chat.append(application_prompt)

while (True):
    user_query = input("User : ")

    user_prompt = {"role": "user", "content": user_query}

    chat.append(user_prompt)
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=chat,
    )
    sql_query = response.choices[0].message.content

    chat.append({"role": "assistant", "content": sql_query})

    # format_print("Generate query :", sql_query)

    db_result = execute_query(sql_query)

    # print(db_result)

    # chat.append(ChatCompletionSystemMessageParam(role="system", content=str(db_result)))

    process_result_query = f"""You are a helpful assistant. 
                                Your task is to process user query and provide them response.
                                A user has asked you this question: {user_query}
                                DBA executed this sql query : {sql_query}
                                This is the result from db: {db_result}
                                Your task is to create a beautiful well structured response for the user"""

    chat.append({"role": "user", "content": process_result_query})
    # print("\n\n\n", chat, "\n\n\n")

    result_response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=chat
    )
    chat.append({"role": "assistant", "content": result_response.choices[0].message.content})

    print("assistant : ", result_response.choices[0].message.content)