from groq import Groq
import json

def call_agent(system_prompt, user_content, api_key):
    """A universal function to call any specific agent in our swarm."""
    client = Groq(api_key=api_key)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        response = client.chat.completions.create(
            messages=messages,
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# --- AGENT 1: THE SQL ENGINEER ---
# ==========================================
def agent_sql_engineer(user_question, schema, api_key):
    system_prompt = (
        "You are an elite Lead Database Engineer. Your ONLY job is to write perfect MySQL queries. "
        "You do not write explanations. You do not make charts. "
        "CRITICAL RULES:\n"
        "1. Only use columns explicitly listed in the schema.\n"
        "2. Use SINGLE QUOTES (') for strings/dates. Never double quotes.\n"
        "3. Pay attention to negative logic (not, exclude).\n"
        "4. Output JSON ONLY.\n"
        "JSON FORMAT:\n"
        "{\n"
        '  "sql": "SELECT ..."\n'
        "}"
    )
    user_content = f"Schema:\n{schema}\n\nQuestion: {user_question}"
    return call_agent(system_prompt, user_content, api_key)

# ==========================================
# --- AGENT 2: THE DATA ANALYST ---
# ==========================================
def agent_data_analyst(user_question, data_sample, api_key):
    system_prompt = (
        "You are a brilliant Data Analyst. You will receive a user's question and a sample of the data returned from the database. "
        "Your job is to explain the data in one short, insightful sentence, and choose the best way to visualize it. "
        "CRITICAL RULES:\n"
        "1. chart_type must be 'table', 'bar', 'line', 'pie', or 'scatter'.\n"
        "2. If not a table, provide exact column names for x_col and y_col based on the data sample keys.\n"
        "JSON FORMAT:\n"
        "{\n"
        '  "explanation": "A short, conversational explanation of the findings.",\n'
        '  "chart_type": "bar",\n'
        '  "x_col": "column_name",\n'
        '  "y_col": "column_name"\n'
        "}"
    )
    # We send the analyst the question AND a stringified version of the data headers/first row
    user_content = f"Question: {user_question}\n\nData Sample:\n{data_sample}"
    return call_agent(system_prompt, user_content, api_key)

# ==========================================
# --- AGENT 3: THE QA DEBUGGER ---
# ==========================================
def agent_qa_debugger(bad_sql, error_message, schema, api_key):
    system_prompt = (
        "You are a Senior SQL Database Administrator. A junior engineer wrote a bad query that crashed. "
        "Your job is to read the bad SQL, read the error message, and write the FIXED SQL query. "
        "CRITICAL RULES:\n"
        "1. Only use columns listed in the schema.\n"
        "2. Use single quotes for strings.\n"
        "3. Output JSON ONLY.\n"
        "JSON FORMAT:\n"
        "{\n"
        '  "sql": "SELECT ..."\n'
        "}"
    )
    user_content = f"Schema:\n{schema}\n\nBad SQL:\n{bad_sql}\n\nError Message:\n{error_message}"
    return call_agent(system_prompt, user_content, api_key)