import os 
from groq import Groq


client = Groq(api_key = "YOUR_API_KEY")

print("Asking AI to write a MySQL Query...\n")

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

user_question = "Find the top 3 highest paid employess in the IT department"


response = client.chat.completions.create(
    messages=[
        {
            # The SYSTEM prompt sets the strict rules. Notice how we forbid explanations.
            "role":"system",
            "content":f"You are an expert MySQL engineer. Based on the provided schema, write a query to answer the user's request. Output strictly the raw SQL code. Do not include markdown formatting (like ```sql). Do not include any explanations."
        },
        {
            # The USER prompt provides the actual data and question
            "role": "user",
            "content": f"Schema:\n{database_schema}\n\nQuestion: {user_question}"
        }
    ],
    model = "llama-3.1-8b-instant",
)

generated_sql = response.choices[0].message.content
print("-----AI Generated Query-----")
print(generated_sql)
print("----------------------------")
