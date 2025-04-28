import os
import logging
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv(dotenv_path=".env.local")

# Configure logging
logger = logging.getLogger("db_initializer")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# PostgreSQL connection setup
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "voice_agent_svc"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "harsh2505"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

# Check if tables exist
def tables_exist(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        return cur.fetchone()[0] > 0

# Initialize database from schema
def initialize_database_from_dump(conn):
    schema_file = "db/schema.sql"
    if not os.path.exists(schema_file):
        logger.error(f"Schema file '{schema_file}' not found!")
        raise FileNotFoundError(f"{schema_file} is missing.")

    logger.info("Initializing database from schema dump...")
    with open(schema_file, "r") as f, conn.cursor() as cur:
        cur.execute(f.read())
    conn.commit()
    logger.info("Database initialized successfully from schema dump.")

# Save participant utility
def save_participant(conn):
    logger.info("Saving participant and generating UUID automatically")
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("INSERT INTO participants (connected_at) VALUES (CURRENT_TIMESTAMP) RETURNING uuid"),
        )
        participant_uuid = cur.fetchone()[0]
        conn.commit()
    return participant_uuid

# Save transcript utility
def save_transcript(conn, participant_uuid, transcript):
    logger.info(f"Saving transcript for participant with UUID {participant_uuid}")
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("INSERT INTO transcripts (participant_id, transcript, recorded_at) VALUES (%s, %s, %s)"),
            [participant_uuid, transcript, datetime.now()]
        )
        conn.commit()

# Save patient details utility
def save_patient_details(conn, patient_name, phone_number, doctor_name_or_specialization, preferred_time_slot):
    """
    Save patient details into the patient_details table.
    """
    try:
        with conn.cursor() as cursor:
            query = """
                INSERT INTO patient_details (patient_name, phone_number, doctor_name_or_specialization, preferred_time_slot)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (patient_name, phone_number, doctor_name_or_specialization, preferred_time_slot))
            conn.commit()
    except Exception as e:
        print(f"Error saving patient details: {e}")
        conn.rollback()

# Main entry point for database initialization
def setup_database():
    conn = get_db_connection()
    try:
        if not tables_exist(conn):
            initialize_database_from_dump(conn)
        else:
            logger.info("Tables already exist; skipping initialization.")
    finally:
        conn.close()
