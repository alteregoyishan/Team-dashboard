"""
Database adapter for Team Dashboard
Supports both SQLite (local) and PostgreSQL (cloud)
"""

import os
import sqlite3
import pandas as pd
from typing import Optional

# Try to import Streamlit for secrets access
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except Exception:
    STREAMLIT_AVAILABLE = False

# Try to import PostgreSQL driver
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

class DatabaseAdapter:
    def __init__(self):
        if STREAMLIT_AVAILABLE and "DATABASE_URL" in st.secrets:
            self.db_url = st.secrets["DATABASE_URL"]
        else:
            self.db_url = os.getenv("DATABASE_URL")                                 
        self.is_postgres = bool(self.db_url and POSTGRES_AVAILABLE)
        
    def get_connection(self):
        """Get database connection based on environment"""
        if self.is_postgres:
            # Cloud PostgreSQL
            try:
                # Add debug info for connection troubleshooting
                if not self.db_url:
                    raise ValueError("DATABASE_URL environment variable is not set")
                
                # Check if URL still contains placeholder
                if '[YOUR-PASSWORD]' in self.db_url:
                    raise ValueError("DATABASE_URL contains placeholder [YOUR-PASSWORD]. Please replace with actual password.")
                
                # Try to connect with additional error info
                conn = psycopg2.connect(
                    self.db_url,
                    connect_timeout=10,
                    sslmode='require'
                )
                conn.autocommit = True
                return conn
            except psycopg2.OperationalError as e:
                # Provide more specific error information
                error_msg = str(e)
                if 'password authentication failed' in error_msg.lower():
                    raise ValueError("Database password is incorrect. Please check your Supabase database password and update DATABASE_URL in Streamlit Secrets.")
                elif 'connection timed out' in error_msg.lower():
                    raise ValueError("Connection timed out. Please check your network connection and Supabase server status.")
                elif 'could not connect' in error_msg.lower():
                    raise ValueError(f"Could not connect to Supabase database. Please verify your DATABASE_URL. Error: {error_msg}")
                else:
                    raise ValueError(f"Database connection failed: {error_msg}")
            except Exception as e:
                raise ValueError(f"Unexpected database connection error: {str(e)}")
        else:
            # Local SQLite
            return sqlite3.connect('team_dashboard.db', check_same_thread=False)
    
    def execute_sql(self, sql: str, params: tuple = (), fetch: bool = False):
        """Execute SQL with proper connection handling"""
        conn = self.get_connection()
        
        try:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()
            
            cursor.execute(sql, params)
            
            if fetch:
                return cursor.fetchall()
            else:
                if not self.is_postgres:
                    conn.commit()
                return cursor.rowcount
        finally:
            conn.close()
    
    def read_sql(self, query: str, params: tuple = ()) -> pd.DataFrame:
        """Read SQL query into DataFrame"""
        conn = self.get_connection()
        try:
            return pd.read_sql_query(query, conn, params=params)
        finally:
            conn.close()
    
    def create_tables(self):
        """Create all required tables with proper syntax"""
        
        if self.is_postgres:
            # PostgreSQL syntax
            tables = [
                """
                CREATE TABLE IF NOT EXISTS task_submissions (
                    id SERIAL PRIMARY KEY,
                    submission_date DATE NOT NULL,
                    user_names TEXT NOT NULL,
                    spatial_completed INTEGER DEFAULT 0,
                    spatial_hours REAL DEFAULT 0.0,
                    spatial_batches TEXT,
                    textual_completed INTEGER DEFAULT 0,
                    textual_hours REAL DEFAULT 0.0,
                    textual_batches TEXT,
                    qa_completed INTEGER DEFAULT 0,
                    qa_hours REAL DEFAULT 0.0,
                    qa_batches TEXT,
                    qc_completed INTEGER DEFAULT 0,
                    qc_hours REAL DEFAULT 0.0,
                    qc_batches TEXT,
                    automation_completed REAL DEFAULT 0.0,
                    automation_hours REAL DEFAULT 0.0,
                    automation_batches TEXT,
                    other_completed INTEGER DEFAULT 0,
                    other_hours REAL DEFAULT 0.0,
                    other_batches TEXT,
                    overtime_hours REAL DEFAULT 0.0,
                    total_hours REAL DEFAULT 0.0,
                    note TEXT,
                    submitted_by TEXT,
                    submit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    spatial_target INTEGER DEFAULT 0,
                    textual_target INTEGER DEFAULT 0,
                    CONSTRAINT check_single_row CHECK (id = 1)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS batch_options (
                    name TEXT PRIMARY KEY
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS team_members (
                    name TEXT PRIMARY KEY,
                    team_function TEXT
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS task_entries (
                    id SERIAL PRIMARY KEY,
                    submission_id INTEGER NOT NULL,
                    submission_date DATE NOT NULL,
                    user_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    batch TEXT NOT NULL,
                    completed REAL DEFAULT 0,
                    hours REAL DEFAULT 0.0,
                    CONSTRAINT fk_submission
                        FOREIGN KEY(submission_id)
                        REFERENCES task_submissions(id)
                        ON DELETE CASCADE
                )
                """
            ]
        else:
            # SQLite syntax
            tables = [
                """
                CREATE TABLE IF NOT EXISTS task_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_date DATE NOT NULL,
                    user_names TEXT NOT NULL,
                    spatial_completed INTEGER DEFAULT 0,
                    spatial_hours REAL DEFAULT 0.0,
                    spatial_batches TEXT,
                    textual_completed INTEGER DEFAULT 0,
                    textual_hours REAL DEFAULT 0.0,
                    textual_batches TEXT,
                    qa_completed INTEGER DEFAULT 0,
                    qa_hours REAL DEFAULT 0.0,
                    qa_batches TEXT,
                    qc_completed INTEGER DEFAULT 0,
                    qc_hours REAL DEFAULT 0.0,
                    qc_batches TEXT,
                    automation_completed REAL DEFAULT 0.0,
                    automation_hours REAL DEFAULT 0.0,
                    automation_batches TEXT,
                    other_completed INTEGER DEFAULT 0,
                    other_hours REAL DEFAULT 0.0,
                    other_batches TEXT,
                    overtime_hours REAL DEFAULT 0.0,
                    total_hours REAL DEFAULT 0.0,
                    note TEXT,
                    submitted_by TEXT,
                    submit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    spatial_target INTEGER DEFAULT 0,
                    textual_target INTEGER DEFAULT 0
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS batch_options (
                    name TEXT PRIMARY KEY
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS team_members (
                    name TEXT PRIMARY KEY,
                    team_function TEXT
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS task_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER NOT NULL,
                    submission_date DATE NOT NULL,
                    user_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    batch TEXT NOT NULL,
                    completed REAL DEFAULT 0,
                    hours REAL DEFAULT 0.0,
                    FOREIGN KEY(submission_id) REFERENCES task_submissions(id) ON DELETE CASCADE
                )
                """
            ]
        
        # Execute table creation
        for sql in tables:
            self.execute_sql(sql)
        
        # Insert default settings
        if self.is_postgres:
            self.execute_sql(
                "INSERT INTO app_settings (id, spatial_target, textual_target) VALUES (1, 0, 0) ON CONFLICT (id) DO NOTHING"
            )
        else:
            self.execute_sql(
                "INSERT OR IGNORE INTO app_settings (id, spatial_target, textual_target) VALUES (1, 0, 0)"
            )

# Global instance
db_adapter = DatabaseAdapter()