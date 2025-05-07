import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import us
import psycopg2
from sqlalchemy import create_engine, text
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load the CSV file
df = pd.read_csv('RewardsData.csv')

# a. Delete the 'tag', 'joined', 'last seen' columns
df = df.drop(columns=['Tags', 'Joined On', 'Last Seen'], errors='ignore')

# b. Fill empty cell on row 438 under the zip column with 11011
df.at[437, 'Zip'] = 11011

# c. Limit zip to 5 digits
df['Zip'] = df['Zip'].astype(str).str[:5]

# d. Convert zip to numeric and fill NaN with mean
df['Zip'] = pd.to_numeric(df['Zip'], errors='coerce')
zip_mean = int(df['Zip'].mean())
df['Zip'] = df['Zip'].fillna(zip_mean).astype(int)

# e. Normalize Winston Salem spelling
df['City'] = df['City'].str.replace('Winston Salem', 'Winston-Salem', regex=False)
df['City'] = df['City'].str.replace('Winston-salem', 'Winston-Salem', regex=False)
df['City'] = df['City'].str.replace('Winston salem', 'Winston-Salem', regex=False)

# f. Remove single-letter abbreviations in city
df['City'] = df['City'].apply(lambda x: '' if isinstance(x, str) and len(x.strip()) == 1 else x)

# g. Replace state abbreviations with full names
state_map = {state.abbr: state.name for state in us.states.STATES}
df['State'] = df['State'].apply(lambda x: state_map.get(x, x))
state_names = [state.name for state in us.states.STATES]
empty_state_cells = df[df['State'].isnull() | (df['State'] == '')].index.tolist()

state_index = 0
for index in empty_state_cells:
    df.loc[index, 'State'] = state_names[state_index]
    state_index = (state_index + 1) % len(state_names)

# h/i. Format birthdates and fill missing ones
df['Birthdate'] = pd.to_datetime(df['Birthdate'], errors='coerce').dt.date

def generate_random_dates(n):
    start_date = datetime(1990, 1, 1)
    end_date = datetime(2010, 12, 31)
    days_between = (end_date - start_date).days
    return [start_date + timedelta(days=random.randint(0, days_between)) for _ in range(n)]

mask = (df['Birthdate'].isnull()) | (df['Birthdate'] == '')
null_count = mask.sum()
df.loc[mask, 'Birthdate'] = [d.date() for d in generate_random_dates(null_count)]

# k. Remove zip rows < 5 digits
df = df[df['Zip'] >= 5]

# l. Fill empty cities with 'Thomas ville'
df['City'] = df['City'].fillna('Thomas ville')
df['City'] = df['City'].replace('', 'Thomas ville')

# Save cleaned data
df.to_csv('processed.csv', index=False)

print("✅ Data cleaned and saved as processed.csv")

# === PostgreSQL Upload Section ===

# Database credentials
user = "postgres"
password = "choice1914"
host = "localhost"
port = "5432"
db_name = "rewards_db"
table_name = "rewards_cleaned"

# 1. Connect to PostgreSQL to create database if it doesn't exist
try:
    connection = psycopg2.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database="postgres"  # connect to default db first
    )
    connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = connection.cursor()

    # Create database if not exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute(f"CREATE DATABASE {db_name}")
        print(f"✅ Database '{db_name}' created.")
    else:
        print(f"ℹ️ Database '{db_name}' already exists.")
    cursor.close()
    connection.close()
except Exception as e:
    print("❌ Error creating database:", e)

# 2. Connect using SQLAlchemy and upload to the table
try:
    engine = create_engine(f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}')
    df.to_sql(table_name, engine, if_exists='replace', index=False)
    print(f"✅ Data uploaded successfully to '{db_name}.{table_name}'")
except Exception as e:
 print("❌ Error uploading data to PostgreSQL:", e)
