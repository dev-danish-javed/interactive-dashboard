# db_chat_utility.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam


class DBChatUtility:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.db_uri = os.getenv("DB_URI")

    def _get_engine(self):
        return create_engine(self.db_uri)

    def get_schema_info(self):
        engine = self._get_engine()
        insp = inspect(engine)
        schema = {}
        for table in insp.get_table_names():
            cols = [col["name"] for col in insp.get_columns(table)]
            schema[table] = cols
        return schema

    def execute_query(self, query: str):
        engine = self._get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
        return rows

    def generate_sql(self, user_query: str) -> str:
        schema = self.get_schema_info()
        db_query_request_messages: list[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
            ChatCompletionSystemMessageParam(
                role="system",
                content=f"""You are an expert Oracle SQL assistant. The database is Oracle DB.
                            Use only the provided schema to answer queries.
                            STRICT OUTPUT RULES:
                            - Output ONLY raw SQL text
                            - No markdown wrapping
                            - No trailing semicolon

                            Schema:\n {schema}
                            """
            ),
            ChatCompletionUserMessageParam(role="user", content=user_query)
        ]
        response = self.client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=db_query_request_messages
        )
        print('\n\n', {'user_query': user_query, 'response': response.choices[0].message.content.strip()}, end='\n\n' )
        return response.choices[0].message.content.strip()

    def process_result(self, user_query: str, sql_query: str, db_result: list) -> str:
        process_result_request = [
            ChatCompletionUserMessageParam(
                role="user",
                content=f"""You are a helpful assistant. 
                            The user asked: {user_query}
                            The SQL query executed: {sql_query}
                            The DB returned: {db_result}
                            Create a structured and beautiful response for the user."""
            )
        ]
        response = self.client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=process_result_request
        )
        return response.choices[0].message.content.strip()

    def run(self, user_query: str) -> str:
        sql_query = self.generate_sql(user_query)
        db_result = self.execute_query(sql_query)
        return self.process_result(user_query, sql_query, db_result)
