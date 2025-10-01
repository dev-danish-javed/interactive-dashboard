import requests
from oracledb import DatabaseError
from sqlalchemy import create_engine, inspect, text
import os
from dotenv import load_dotenv

load_dotenv()
# ---- CONFIG ----
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
ENDPOINT_oLD = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

DB_URI = "oracle+oracledb://paymentus:paymentusp@localhost:1521/?service_name=FREEPDB1"

engine = create_engine(DB_URI)



# ---- GEMINI CALL ----
def ask_gemini(prompt: str) -> str:
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(ENDPOINT, json=body)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ---- DB SCHEMA UTILS ----
def get_schema_info():
    insp = inspect(engine)
    schema = {}
    for table in insp.get_table_names():
        cols = [col["name"] for col in insp.get_columns(table)]
        schema[table] = cols
    return schema


# ---- CHAT LOOP ----
def chatbot(question: str):
    # 1. Get schema snapshot
    schema = get_schema_info()

    # 2. Build prompt with only schema metadata
    schema_text = "\n".join([f"{t}: {', '.join(c)}" for t, c in schema.items()])
    prompt = f"""
                You are an expert Oracle SQL assistant. The database you are working on is oracle db.

                Schema:
                {schema_text}
                
                User question: {question}
                
                Return only the oracle db sql query without the semicolone. Don't wrap the query in markdown.
    """

    # 3. Ask Gemini
    sql = ask_gemini(prompt).strip()
    print(f'first sql : {sql}')
    try:
        # 4. Execute
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
        return prepare_results(prompt, sql, rows)
    except Exception as e:
        return prepare_results(prompt, sql, handleError(prompt, sql, e))


def handleError(prompt: str, sql_query : str, error: DatabaseError):
    error_prompt = f"""
    You are an expert Oracle DB DBA. Based on the prompt, you provided a sql query. That query ran into error.
    Based on the error, provide an updated query.
    
    -- Prompt starts here
    The prompt : 
    {prompt}
    
    -- Prompt ends here
    
    -- Query starts here
    The query : 
    {sql_query}
    
    -- Query ends here
    
    -- The error starts here
    The error : {error.args[0]}
    
    -- The error ends here
    
    Make sure to not include any explainations.
    """
    updated_sql = ask_gemini(error_prompt).strip()
    print(f'first sql : {updated_sql}')
    # 4. Execute
    with engine.connect() as conn:
        result = conn.execute(text(updated_sql))
        rows = result.fetchall()
    return rows

def prepare_results(user_query: str, sql_query: str, result):
    result_prompt = f"""
    You are a chatbot. You take user query in natural language. You prepare a sql query. Sql query is then executed and you recieve the result.
    This is the final stage of processing. You have the user query, sql query and the result. Create a well crafted response for the user in natural language.
    
    -- User query starts here
    Uer query: 
    {user_query}
    
    -- User query ends here
    
    
    -- sql query starts here
    The sql query : 
    {sql_query}
    
    -- sql query ends here
    
    -- result starts here
    The result : 
    {result}
    
    -- result ends here
    
    Don't add any context or salutaion. Return a plain text response that is user focused
    
    """
    gemini_response = ask_gemini(result_prompt).strip()
    print("Chatbot : ", gemini_response)

# ---- Example ----
user_query = "Give me the top 2 users that have made most payment"
print("User Query :", user_query)
chatbot(user_query)
