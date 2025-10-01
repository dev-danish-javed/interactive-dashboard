from openai import OpenAI
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


def format_print(key: str, value: str):
    print(key.center(20, "="))
    print(value)
    print("=".center(20, "="), end="\n\n")


def get_schema_info():
    engine = create_engine(os.getenv("DB_URI"))
    insp = inspect(engine)
    schema = {}
    for table in insp.get_table_names():
        cols = [col["name"] for col in insp.get_columns(table)]
        schema[table] = cols
    schema_text = "\n".join([f"{t}: {', '.join(c)}" for t, c in schema.items()])
    return schema_text


def execute_query(query):
    engine = create_engine(os.getenv("DB_URI"))
    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.fetchall()
    return rows

chat = []

while(True):
    user_query = input("User : ")

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
    
                        Below is the oracle db schema :\n {get_schema_info()}
                        """}

    user_prompt = {"role" : "user", "content" : user_query}
    chat.append(application_prompt)
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

    chat.append({"role":"user", "content": process_result_query})
    # print("\n\n\n", chat, "\n\n\n")

    result_response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=chat
    )
    chat.append({"role":"assistant", "content": result_response.choices[0].message.content})


    print("assistant : ",result_response.choices[0].message.content)