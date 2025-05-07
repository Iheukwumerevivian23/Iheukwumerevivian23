import psycopg2

# Database connection parameters
host = "localhost"
user = "postgres"
password = "choice1914"
port = 5432
import psycopg2


try:
    # Step a: Create new database 'my_database'
    conn = psycopg2.connect(dbname='postgres', user=user, password=password, host=host, port=port)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS my_database;")
    cur.execute("CREATE DATABASE my_database;")
    print("Database 'my_database' created.")
    cur.close()
    conn.close()

    # Step b: Connect to 'my_database' and create schema 'new_schema'
    conn = psycopg2.connect(dbname='my_database', user=user, password=password, host=host, port=port)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS new_schema;")
    print("Schema 'new_schema' created.")

    # Step c: Connect to 'dvd_rentals' and read data from 'film' table
    conn_dvd = psycopg2.connect(dbname='dvd_rentals', user=user, password=password, host=host, port=port)
    cur_dvd = conn_dvd.cursor()
    cur_dvd.execute("SELECT * FROM film;")
    films = cur_dvd.fetchall()
    colnames = [desc[0] for desc in cur_dvd.description]

    # Fetch detailed column info to build CREATE TABLE statement
    cur_dvd.execute("""
        SELECT 
            a.attname AS column_name,
            t.typname AS type_name,
            t.typcategory,
            a.atttypmod
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        JOIN pg_type t ON a.atttypid = t.oid
        WHERE c.relname = 'film' AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum;
    """)
    columns = cur_dvd.fetchall()

    column_defs = []
    for name, typname, typcat, typmod in columns:
        if name == 'release_year':
            column_defs.append(f"{name} SMALLINT")  # Fix 'YEAR' type
        elif typname == 'varchar' and typmod > 0:
            size = typmod - 4
            column_defs.append(f"{name} VARCHAR({size})")
        elif typcat == 'E':  # ENUM or user-defined
            column_defs.append(f"{name} VARCHAR")
        elif typname.startswith('_'):  # ARRAY type
            base_type = typname[1:]
            column_defs.append(f"{name} {base_type.upper()}[]")
        else:
            column_defs.append(f"{name} {typname.upper()}")

    # Create film1 table
    cur.execute("DROP TABLE IF EXISTS new_schema.film1 CASCADE;")
    create_stmt = f"CREATE TABLE new_schema.film1 ({', '.join(column_defs)});"
    cur.execute(create_stmt)
    print("Table 'film1' created in 'new_schema'.")

    # Step d: Insert data into film1
    insert_stmt = f"""
        INSERT INTO new_schema.film1 ({', '.join(colnames)})
        VALUES ({', '.join(['%s'] * len(colnames))})
    """
    cur.executemany(insert_stmt, films)
    print("Data inserted into 'film1'.")

    # Step e: Create my_data table with aggregate values
    cur.execute("DROP TABLE IF EXISTS new_schema.my_data;")
    cur.execute("""
        CREATE TABLE new_schema.my_data (
            tot_row INTEGER,
            dist_rating INTEGER,
            tot_length INTEGER,
            avg_length NUMERIC,
            round_avg NUMERIC
        );
    """)

    cur.execute("""
        SELECT
            COUNT(*) AS tot_row,
            COUNT(DISTINCT rating) AS dist_rating,
            SUM(length) AS tot_length,
            AVG(length) AS avg_length,
            ROUND(AVG(length), 2) AS round_avg
        FROM new_schema.film1;
    """)
    stats = cur.fetchone()

    cur.execute("""
        INSERT INTO new_schema.my_data (tot_row, dist_rating, tot_length, avg_length, round_avg)
        VALUES (%s, %s, %s, %s, %s);
    """, stats)
    print("Aggregate data inserted into 'my_data'.")

    # Cleanup
    cur.close()
    conn.close()
    cur_dvd.close()
    conn_dvd.close()
    print("✅ All tasks completed successfully.")

except Exception as e:
    print("❌ Error:", e)