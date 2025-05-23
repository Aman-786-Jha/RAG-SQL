import psycopg2
from faker import Faker
import random
from datetime import datetime, timedelta
import os

from dotenv import load_dotenv
load_dotenv()


DB_NAME=os.getenv("DB_NAME")
DB_USER=os.getenv("DB_USER")
DB_PASSWORD=os.getenv("DB_PASSWORD")
DB_HOST=os.getenv("DB_HOST")
DB_PORT=os.getenv("DB_PORT")

fake = Faker()


conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)
cur = conn.cursor()


departments = ['HR', 'Engineering', 'Marketing', 'Sales', 'Finance', 'Operations']
for dept in departments:
    cur.execute("INSERT INTO departments (name) VALUES (%s);", (dept,))
conn.commit()


cur.execute("SELECT id FROM departments;")
department_ids = [row[0] for row in cur.fetchall()]


for _ in range(50):
    name = fake.name()
    dept_id = random.choice(department_ids)
    email = fake.email()
    salary = round(random.uniform(30000, 120000), 2)
    cur.execute(
        "INSERT INTO employees (name, department_id, email, salary) VALUES (%s, %s, %s, %s);",
        (name, dept_id, email, salary)
    )
conn.commit()


cur.execute("SELECT id FROM employees;")
employee_ids = [row[0] for row in cur.fetchall()]

for _ in range(50):
    product_name = fake.word().capitalize()
    price = round(random.uniform(10, 500), 2)
    cur.execute(
        "INSERT INTO products (name, price) VALUES (%s, %s);",
        (product_name, price)
    )
conn.commit()

for _ in range(50):
    customer_name = fake.name()
    emp_id = random.choice(employee_ids)
    order_total = round(random.uniform(100, 5000), 2)
    order_date = fake.date_between(start_date='-1y', end_date='today')
    cur.execute(
        "INSERT INTO orders (customer_name, employee_id, order_total, order_date) VALUES (%s, %s, %s, %s);",
        (customer_name, emp_id, order_total, order_date)
    )
conn.commit()

cur.close()
conn.close()

print("Dummy data inserted successfully.")
