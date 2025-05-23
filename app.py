import streamlit as st


st.set_page_config(
    page_title="Natural Language to SQL",
    page_icon="🔍",
    layout="centered"
)

import psycopg2
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import pandas as pd
import re
import psycopg2
from datetime import datetime, timedelta, date

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="baseButton-headerNoPadding"] {display: none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("""
    <style>
    .char-count {
        font-size: 14px;
        color: red;
        margin-top: -10px;
        margin-bottom: 10px;
    }
    </style>
    <script>
    const textarea = window.parent.document.querySelector('textarea');
    const info = document.createElement('div');
    info.className = 'char-count';
    textarea.parentElement.appendChild(info);
    textarea.addEventListener('input', function() {
        const maxChars = 300;
        if (this.value.length >= maxChars) {
            this.value = this.value.slice(0, maxChars);
            info.textContent = "❗ Maximum 300 characters allowed!";
        } else {
            info.textContent = "";
        }
    });
    </script>
""", unsafe_allow_html=True)




load_dotenv()

genai_api_key = os.getenv("GENAI_API_KEY")

genai.configure(api_key=genai_api_key)

generation_config = {
    "temperature": 0.1,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings,
)


def connect_db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

def get_api_usage():
    conn = connect_db()
    cur = conn.cursor()
    today = date.today()
    cur.execute("SELECT request_count FROM api_usage WHERE date = %s", (today,))
    result = cur.fetchone()
    if result:
        request_count = result[0]
    else:
        cur.execute("INSERT INTO api_usage (date, request_count) VALUES (%s, %s)", (today, 0))
        conn.commit()
        request_count = 0
    cur.close()
    conn.close()
    return request_count


def increment_api_usage():
    conn = connect_db()
    cur = conn.cursor()
    today = date.today()
    cur.execute("UPDATE api_usage SET request_count = request_count + 1 WHERE date = %s", (today,))
    conn.commit()
    cur.close()
    conn.close()

MAX_REQUESTS_PER_DAY = 10


query_generation_prompt = """
You are an expert SQL generator and having 25+ years of experience in SQL so do all thing related to the accordingly to your experience holder. Only generate SELECT queries based on the following schema.

Schema:
- departments(id, name)
- employees(id, name, department_id, email, salary)
- products(id, name, price)
- orders(id, customer_name, employee_id, order_total, order_date)

Relationships:
- employees.department_id → departments.id
- orders.employee_id → employees.id

DO NOT generate any DELETE, UPDATE, INSERT or DDL queries.
Return only SELECT queries based on user's natural language question.

User could input in any language so handle there prompt in efficient way and with understanding what user is saying you will generate sql query with above instructions.

User input: {user_query}
"""

query_validation_prompt = """
You are a SQL inspector which has the experience of 25+ years in the field of keeping the database secure and always ensure not touch any part in the databse.So just retrieving or reading of data is allowed to perform.
Check the following SQL query and tell if it is a pure SELECT query with no DML or DDL actions.
Respond in JSON like: {{"safe_to_run": "yes"}} or {{"safe_to_run": "no"}}
SQL Query: {sql_query}
"""

import re

def extract_json(text):
    try:
        json_text = re.search(r"\{.*\}", text, re.DOTALL).group()
        return json.loads(json_text)
    except Exception as e:
        print("JSON extract/parse error:", e)
        return None
    
import re

def clean_sql_query(query):
    query = re.sub(r"```(?:sql)?", "", query)
    return query.strip()


def run_query(query):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    return columns, rows

def log_to_json(user_input, generated_sql):
    log_entry = {
        "user_input": user_input,
        "generated_sql": generated_sql if generated_sql.strip().lower().startswith("select") else "no sql generated"
    }

    json_file = "query_log.json"

    if not os.path.exists(json_file):
        with open(json_file, "w") as f:
            json.dump([log_entry], f, indent=4)
    else:
        with open(json_file, "r+") as f:
            data = json.load(f)
            data.append(log_entry)
            f.seek(0)
            json.dump(data, f, indent=4)


st.title("🔍 Natural Language to SQL using Gemini - Secure RAG")

# user_input = st.text_input("💬 Ask your question (any language):")
user_input = st.text_area("💬 Ask your question (any language e.g English, Hindi etc):", max_chars=300)

if st.button("Generate SQL and Run") and user_input.strip():
    with st.spinner("🧠 Generating SQL using Gemini..."):

        if get_api_usage() >= MAX_REQUESTS_PER_DAY:
            reset_time = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
            st.error(f"🚫 API request limit exceeded. Try again after {reset_time.strftime('%Y-%m-%d %H:%M:%S')}")
            st.stop()


        increment_api_usage()
        prompt = query_generation_prompt.format(user_query=user_input)
        print('prompt---------->', prompt)
        response = model.generate_content(prompt)
        print('response------------->', response)
        # generated_sql = response.text.strip()
        generated_sql = clean_sql_query(response.text)
        # log_to_json(user_input, generated_sql)


        print('generated_sql-------------->', generated_sql)

        validation_prompt = query_validation_prompt.format(sql_query=generated_sql)
        print('validation_prompt----------->', validation_prompt)
        validation = model.generate_content(validation_prompt)
        print('validation------------>', validation)
        try:
            # validation_json = json.loads(validation.text.strip())
            validation_json = extract_json(validation.text.strip())

            print('validation_json------------->', validation_json)
        except Exception as e:
            print('validation_error------------->', e)
            st.error("❌ Failed to validate SQL safely.")
            st.stop()

        if not validation_json:
            log_to_json(user_input, "no sql generated")
            st.error("❌ Failed to parse validation response as JSON.")
            st.stop()

        log_to_json(user_input, generated_sql)

        if validation_json.get("safe_to_run", "no") == "yes" and generated_sql.strip().lower().startswith("select"):
            print('yahan chla------------>')
            st.code(generated_sql, language='sql')
            try:
                cols, data = run_query(generated_sql)
                df = pd.DataFrame(data, columns=cols)
                st.success("✅ Query executed successfully.")
                st.dataframe(df)

                explanation_prompt = f"""
                You are an expert data analyst having 25+ years of experience in the field and you have to answers or summarize beautifully accordingly as of you holding the immense experience.

                A user asked: "{user_input}"

                Based on the following schema:
                Schema:
                - departments(id, name)
                - employees(id, name, department_id, email, salary)
                - products(id, name, price)
                - orders(id, customer_name, employee_id, order_total, order_date)

                Relationships:
                - employees.department_id → departments.id
                - orders.employee_id → employees.id

                The generated SQL was:
                {generated_sql}

                And the output of the query was:
                Columns: {cols}
                Data: {data}

                Explain this result in simple and clear language and in which language user asked or input the question only in that you have to explain, For example if user has inputted in english then in english you have to explain, if in hindi then in hindi you have to explain etc. . Mention what the result represents in relation to the user's original question.
                """

                explanation = model.generate_content(explanation_prompt)
                st.markdown("### 🤖 Explanation")
                st.write(explanation.text)

            except Exception as e:
                st.error(f"❌ 400 Bad Request: something not good happened...")
                print('sql running query error---------->', e)
        else:
            st.warning("🚫 Unsafe or invalid query detected. Only valid inputs are allowed.")
