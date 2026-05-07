import os
from groq import Groq
import mysql.connector
from mysql.connector import Error


# --- CONFIGURATION (Put your credentials here) ---
GROQ_API_KEY = "YOUR_API_KEY"
DB_HOST = 'localhost'
DB_USER = ''
DB_PASSWORD = ''
DB_NAME = 'project_a'


# --- THE BRAIN: AI Translator ---
def get_sql_from_ai(user_question):
    print(f"Brain : Thinking about how to answer : \n'{user_question}'....\n")
    client = Groq(api_key = GROQ_API_KEY)

    database_schema = """
        Table Name: employees
        Columns:
        - employee_id (INT)
        - first_name (VARCHAR)
        - last_name (VARCHAR)
        - department (VARCHAR)
        - salary (INT)
        - hire_date (DATE)
    """

    response = client.chat.completions.create(
        messages=[
            {
                "role":"system",
                "content": (
                    "You are an expert MySQL engineer. Your job is to translate casual human language "
                    "into precise SQL queries based STRICTLY on the provided schema. "
                    "CRITICAL RULES FOR MAPPING: "
                    "1. If the user asks for 'name', you must inspect the schema. "
                    "2. Prioritize using 'first_name' if it exists. "
                    "3. If 'first_name' does NOT exist in the schema, you must fallback to using 'last_name'. "
                    "4. NEVER invent or guess column names. Only use exact matches from the schema. "
                    "Output strictly the raw SQL code. Do not include markdown formatting (like ```sql). "
                    "Do not include any explanations."
                )
            },
            {
                "role": "user",
                "content": f"Schema:\n{database_schema}\n\nQuestion: {user_question}"
            }
        ],
        model="llama-3.1-8b-instant",
    )


    sql_query = response.choices[0].message.content.strip()
    return sql_query



# ---------- THE HANDS : Database Executor --------- #
def execute_sql_and_print(sql_query):
    print(f"Hands: Executing Query on MySQL -> \n{sql_query}\n")

    try:
        connection = mysql.connector.connect(
            host = DB_HOST,
            user = DB_USER,
            password = DB_PASSWORD,
            database = DB_NAME
        )

        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute(sql_query)
            row = cursor.fetchall()

            print("\n ----FINAL RESULT ----")
            if not row:
                print("No data found")
            else:
                for rows in row:
                    print(rows)
            print("----------------------- END ---------------------")

    except Error as e:
        print("Database error : ",e)
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    print("AI Data Analyst Booted Up! (Type 'exit' to quit)")
    print("-"*50)

    while True:
        question = input("\nEnter what to do: ")

        if question.strip().lower() in ['exit','quit']:
            print("Shutting down... Good Bye")
            break
            
        generated_sql = get_sql_from_ai(question)

        # -----  THE SECURITY GAURD ----- #
        forbidden_words = ['drop','delete','truncate','update','insert','alter']

        is_safe = True
        for word in forbidden_words:
            if word in generated_sql.lower():
                is_safe = False
                break

        if is_safe:
            execute_sql_and_print(generated_sql)
        else:
            print("\n  # SECURITY ALERT # \n")
            print(f"The AI attempeted to run destructive command:")
            print(f" -> {generated_sql} ")
            print("Execution is blocked. This agent is strictly READ-ONLY")