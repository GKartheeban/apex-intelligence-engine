import streamlit as st
import pandas as pd
import mysql.connector
from groq import Groq
import time
import json
import plotly.express as px


# ==========================================
# --- SECURE CONFIGURATION (CLOUD NODE) ---
# ==========================================
DB_HOST = st.secrets["aiven"]["host"]
DB_USER = st.secrets["aiven"]["user"]
DB_PASSWORD = st.secrets["aiven"]["password"]
DB_PORT = st.secrets["aiven"]["port"]

# ==========================================
# --- HELPER HANDS ---
# ==========================================
@st.cache_data(ttl=60)
def get_available_databases():
    try:
        conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES WHERE 'database' NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys'); ")
        dbs = [row[0] for row in cursor.fetchall() if row[0] not in ('information_schema', 'mysql', 'performance_schema', 'sys')]
        conn.close()
        return dbs
    except Exception as e:
        return []

def get_dynamic_schema(db_name):
    try:
        conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=db_name)
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]
        
        schema_string = ""
        for table in tables:
            cursor.execute(f"DESCRIBE {table};")
            columns = [row[0] for row in cursor.fetchall()]
            schema_string += f"Table: {table} | Columns: {columns}\n"
            
        conn.close()
        return schema_string.strip()
    except Exception as e:
        return "Schema unavailable."

def execute_sql_for_web(sql_query, db_name):
    try:
        connection = mysql.connector.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=db_name
        )
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute(sql_query)
            
            # Check if the query is a SELECT (returns data) or an ACTION (CREATE/INSERT/etc)
            if cursor.description is not None:
                # It's a SELECT query: return a DataFrame
                columns = [col[0] for col in cursor.description]
                data = cursor.fetchall()
                df = pd.DataFrame(data, columns=columns)
                return df, None
            else:
                # It's an ACTION query: Commit changes and return a special success flag
                connection.commit()
                return "SUCCESS_ACTION", None
    except Exception as e:
        return None, str(e)
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

# ==========================================
# --- THE BRAIN (Now with JSON & Memory!) ---
# ==========================================
def get_ai_response(user_question, api_key, current_schema, chat_history):
    client = Groq(api_key=api_key)
    
    # 1. Build the system rules to force JSON output
    # 1. Build the system rules to force JSON output
    # 1. Build the system rules to force JSON output AND advanced logic
    # 1. Build the system rules to force JSON output AND advanced logic
    messages = [
        {
            "role":"system",
            "content": (
                "You are an elite SQL and Data Visualization AI. "
                "You must respond ONLY with a raw JSON object. Do not use markdown ```json blocks. "
                "CRITICAL RULES:\n"
                "1. ONLY use columns explicitly listed in the dynamic schema provided.\n"
                "2. DO NOT output 'USE database;' commands.\n"
                "3. If asked to list databases, the sql MUST BE: SELECT schema_name AS 'Available Databases' FROM information_schema.schemata;\n"
                "4. If asked to list tables, the sql MUST BE: SELECT table_name AS 'Available Tables' FROM information_schema.tables WHERE table_schema = DATABASE();\n"
                "5. Analyze the user's request: if they ask for a chart, set chart_type to 'bar', 'line', 'pie', or 'scatter'. Otherwise, use 'table'.\n"
                "6. If chart_type is not 'table', provide the exact column names for x_col and y_col based on your SQL query.\n"
                "7. NEGATIVE LOGIC: Pay strict attention to negative constraints (like 'not', 'exclude', 'except'). Translate these into explicit SQL exclusion operators (!=, <>, NOT IN).\n"
                "8. SQL SYNTAX: You MUST use Single Quotes (') for all string and date literals. NEVER use Double Quotes (\") for values, or the query will crash.\n"
                "JSON FORMAT MUST BE EXACTLY:\n"
                "{\n"
                '  "sql": "SELECT...",\n'
                '  "chart_type": "table",\n'
                '  "x_col": "column_name_or_null",\n'
                '  "y_col": "column_name_or_null",\n'
                '  "explanation": "A short, conversational sentence explaining what you found."\n'
                "}"
            )
        }
    ]
    
    # 2. Add the Chat Memory (so it remembers follow-up questions!)
    for msg in chat_history[-4:]: # We keep the last 4 messages to save tokens
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    # 3. Add the current question and schema
    messages.append({
        "role": "user",
        "content": f"Schema:\n{current_schema}\n\nQuestion: {user_question}"
    })

    # 4. Make the call
    response = client.chat.completions.create(
        messages=messages,
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"} # Forces Llama to output JSON!
    )
    
    # Safely parse the JSON
    try:
        return json.loads(response.choices[0].message.content.strip())
    except Exception:
        return {"sql": "", "explanation": "Error formatting JSON response.", "chart_type": "table"}

# ==========================================
# --- THE UI: MAIN APPLICATION ---
# ==========================================
st.set_page_config(page_title="Apex Digital | Data Core", page_icon="🏔️", layout="wide")

# --- AUTHENTICATION GATEKEEPER ---
@st.dialog("🔐 Apex Digital | Secure Login")
def login_screen():
    st.markdown("Welcome back. Please authenticate to access the intelligence engine.")
    entered_username = st.text_input("Username")
    entered_password = st.text_input("Password", type="password")
    
    if st.button("Access System 🚀"):
        if (entered_username == st.secrets["admin_login"]["username"] and 
            entered_password == st.secrets["admin_login"]["password"]):
            st.session_state.authenticated = True
            st.session_state.groq_key = st.secrets["GROQ_API_KEY"]
            st.rerun() 
        else:
            st.error("❌ Access Denied: Invalid credentials.")

if "authenticated" not in st.session_state:
    login_screen()
    st.stop()

# # --- INITIALIZE MEMORY ---
# if "chat_history" not in st.session_state:
#     st.session_state.chat_history = []
if "db_chat_histories" not in st.session_state:
    st.session_state.db_chat_histories = {} # This is now a Dictionary (Filing Cabinet)

# --- SIDEBAR ---
# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 📡 Connection Status")
    st.success("🟢 AI Engine Online")
    
    # --- RESTORED SERVER DETAILS ---
    st.markdown("#### 🗄️ Database Selection")
    available_dbs = get_available_databases()
    
    if available_dbs:
        selected_db = st.selectbox("Active Database:", available_dbs)
        current_schema = get_dynamic_schema(selected_db)
        
        # --- NEW: Open the specific folder for this database! ---
        if selected_db not in st.session_state.db_chat_histories:
            st.session_state.db_chat_histories[selected_db] = []
            
        with st.expander("👀 View Dynamic Schema"):
            st.code(current_schema, language="text")
    else:
        st.error("No databases found.")
        st.stop()
        
    st.divider()
    if st.button("🗑️ Clear Chat History"):
        # Now this button ONLY clears the active database's history!
        st.session_state.db_chat_histories[selected_db] = []
        st.rerun()

# --- MAIN DASHBOARD ---
st.title("🏔️ Apex Digital | Intelligence Engine")
st.markdown(f"**Enterprise Data Analysis.** Currently connected to: **`{selected_db}`**.")

# 1. Render all previous chat messages and charts from Memory!
for msg in st.session_state.db_chat_histories[selected_db]
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        
        # If this message has data, draw the table or chart!
        if "df" in msg and msg["df"] is not None:
            df = msg["df"]
            c_type = msg.get("chart_type", "table")
            
            # --- THE FIX: Check if it is our Action Success string first! ---
            if isinstance(df, str) and df == "SUCCESS_ACTION":
                st.success("✅ Database action executed successfully!")
            
            # --- Otherwise, if it is a real DataFrame, draw the charts/tables ---
            elif isinstance(df, pd.DataFrame) and not df.empty:
                if c_type == "bar" and msg.get("x_col") and msg.get("y_col"):
                    st.plotly_chart(px.bar(df, x=msg["x_col"], y=msg["y_col"]), use_container_width=True)
                elif c_type == "line" and msg.get("x_col") and msg.get("y_col"):
                    st.plotly_chart(px.line(df, x=msg["x_col"], y=msg["y_col"]), use_container_width=True)
                elif c_type == "pie" and msg.get("x_col") and msg.get("y_col"):
                    st.plotly_chart(px.pie(df, names=msg["x_col"], values=msg["y_col"]), use_container_width=True)
                else:
                    st.dataframe(df, use_container_width=True)
# 2. Chat Input
question = st.chat_input("👤 Ask a question (e.g., 'Show me a bar chart of salaries by department')")

if question:
    # Add user question to memory and display it
    st.session_state.db_chat_histories[selected_db].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
        
    with st.chat_message("assistant"):
        with st.spinner("Analyzing data and generating visuals..."):
            
            # The AI reads the memory, the schema, and writes the JSON blueprint
            ai_data = get_ai_response(question, st.session_state.groq_key, current_schema, st.session_state.db_chat_histories[selected_db])
            
            sql_query = ai_data.get("sql", "")
            explanation = ai_data.get("explanation", "Here is what I found:")
            chart_type = ai_data.get("chart_type", "table")
            x_col = ai_data.get("x_col")
            y_col = ai_data.get("y_col")
            
            # Display the AI's conversational explanation
            st.write(explanation)
            with st.expander("🔍 View SQL Query"):
                st.code(sql_query, language="sql")
            
            # Execute and Render
            if sql_query:
                df, error = execute_sql_for_web(sql_query, selected_db)
                
                if error:
                    st.error(f"❌ Database Error: {error}")
                
                # 1. Check if df is a string FIRST. 
                # Python will short-circuit here if df is a DataFrame, avoiding the error!
                elif isinstance(df, str) and df == "SUCCESS_ACTION":
                    st.success("✅ Database action executed successfully!")
                
                # 2. Now it is completely safe to check if we have a non-empty DataFrame
                elif isinstance(df, pd.DataFrame) and not df.empty:
                    # Render the correct visual based on AI's instructions
                    if chart_type == "bar" and x_col and y_col:
                        st.plotly_chart(px.bar(df, x=x_col, y=y_col), use_container_width=True)
                    elif chart_type == "line" and x_col and y_col:
                        st.plotly_chart(px.line(df, x=x_col, y=y_col), use_container_width=True)
                    elif chart_type == "pie" and x_col and y_col:
                        st.plotly_chart(px.pie(df, names=x_col, values=y_col), use_container_width=True)
                    else:
                        st.dataframe(df, use_container_width=True)
                
                else:
                    st.warning("Query executed successfully, but no data was returned.")
                
                # Save the results to Memory so they stay on screen!
                # Save the results to Memory so they stay on screen!
                st.session_state.db_chat_histories[selected_db].append({
                    "role": "assistant", 
                    "content": explanation,
                    "df": df,
                    "chart_type": chart_type,
                    "x_col": x_col,
                    "y_col": y_col
                })