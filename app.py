import streamlit as st
import pandas as pd
import mysql.connector
from groq import Groq
import time
import json
import plotly.express as px
from swarm import agent_sql_engineer, agent_data_analyst


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
# --- MULTI-AGENT SWARM COORDINATOR ---
# ==========================================
def run_data_swarm(user_question, api_key, current_schema, db_name):
    # 1. AGENT 1: Write the SQL
    sql_data = agent_sql_engineer(user_question, current_schema, api_key)
    sql_query = sql_data.get("sql", "")

    if not sql_query:
        return {"error": "The SQL Engineer failed to write a query.", "sql": ""}

    # 2. THE SYSTEM: Execute the Query safely against Aiven
    df, db_error = execute_sql_for_web(sql_query, db_name)

    if db_error:
        return {"error": f"Database Error: {db_error}", "sql": sql_query}

    # 3. PREPARE THE DATA SAMPLE
    # We only send the first 3 rows to the Analyst so we don't overwhelm its memory!
    if isinstance(df, pd.DataFrame) and not df.empty:
        data_sample = str(df.head(3).to_dict(orient="records"))
    elif isinstance(df, str) and df == "SUCCESS_ACTION":
        data_sample = "Database action executed successfully. (No table returned)"
    else:
        data_sample = "The query ran successfully, but returned 0 rows of data."

    # 4. AGENT 2: Read the actual data and write the Explanation & Pick the Chart
    analyst_data = agent_data_analyst(user_question, data_sample, api_key)

    # 5. Package it all up for the UI
    return {
        "sql": sql_query,
        "df": df,
        "explanation": analyst_data.get("explanation", "Here is the data you requested."),
        "chart_type": analyst_data.get("chart_type", "table"),
        "x_col": analyst_data.get("x_col"),
        "y_col": analyst_data.get("y_col")
    }




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
for msg in st.session_state.db_chat_histories[selected_db]:
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
        with st.spinner("The Agent Swarm is analyzing your request..."):
            
            # 1. WAKE UP THE SWARM
            swarm_result = run_data_swarm(question, st.session_state.groq_key, current_schema, selected_db)
            
            # 2. Check for Errors from Agent 1 or the Database
            if "error" in swarm_result:
                st.error(swarm_result["error"])
                if swarm_result.get("sql"):
                    with st.expander("🔍 View Failed SQL"):
                        st.code(swarm_result["sql"], language="sql")
            
            # 3. Render the Success from Agent 2!
            else:
                df = swarm_result["df"]
                explanation = swarm_result["explanation"]
                chart_type = swarm_result["chart_type"]
                x_col = swarm_result["x_col"]
                y_col = swarm_result["y_col"]
                
                st.write(explanation)
                with st.expander("🔍 View SQL Query"):
                    st.code(swarm_result["sql"], language="sql")
                
                # Render the correct visual
                if isinstance(df, str) and df == "SUCCESS_ACTION":
                    st.success("✅ Database action executed successfully!")
                elif isinstance(df, pd.DataFrame) and not df.empty:
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
                
                # Save the results to Memory
                st.session_state.db_chat_histories[selected_db].append({
                    "role": "assistant", 
                    "content": explanation,
                    "df": df,
                    "chart_type": chart_type,
                    "x_col": x_col,
                    "y_col": y_col
                })