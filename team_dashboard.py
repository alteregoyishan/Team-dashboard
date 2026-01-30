import streamlit as st
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import sqlite3
import json
from typing import List, Dict
import io

# Import database adapter for cloud compatibility
try:
    from database_adapter import db_adapter
    USE_CLOUD_DB = True
except ImportError:
    USE_CLOUD_DB = False

# Page configuration
st.set_page_config(
    page_title="Team Performance Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# User list - Update this with your actual team members

USER_LIST = []


# Default batch options
DEFAULT_BATCH_OPTIONS = [
    "CRAWLEYBOROUGHCOUNCIL_94",
    "CRAWLEYBOROUGHCOUNCIL_95",
    "GATESHEADBOROUGHCOUNCIL_96",
    "GATESHEADBOROUGHCOUNCIL_97",
    "EXETERCITYCOUNCIL_98"
]

# Admin access code (set ADMIN_ACCESS_CODE env var to override)
ADMIN_ACCESS_CODE = os.getenv("ADMIN_ACCESS_CODE", "PM_ADMIN")

def load_users_from_file():
    """Load users from PM.xlsx or PM_users.txt file or default list"""
    try:
        # Prefer PM.xlsx if it exists
        if os.path.exists('PM.xlsx'):
            df = pd.read_excel('PM.xlsx')
            # Try common column names for user list
            user_col = None
            for col in df.columns:
                col_norm = str(col).strip().lower()
                if col_norm in {'name', 'user name', 'username', 'user'}:
                    user_col = col
                    break
            if user_col:
                users = (
                    df[user_col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )
                users = [u for u in users if u]
                if users:
                    return users

        # Fallback to PM_users.txt
        with open('PM_users.txt', 'r', encoding='utf-8') as f:
            users = [line.strip() for line in f.readlines() if line.strip()]
            return users if users else USER_LIST
    except FileNotFoundError:
        return USER_LIST
    except Exception:
        return USER_LIST

def save_users_to_file(users):
    """Save users to PM_users.txt file"""
    try:
        with open('PM_users.txt', 'w', encoding='utf-8') as f:
            for user in users:
                f.write(f"{user}\n")
        return True
    except Exception:
        return False

def get_database_connection():
    """Get database connection with cloud compatibility"""
    if USE_CLOUD_DB:
        # Use cloud database adapter
        return db_adapter.get_connection()
    else:
        # Fallback to SQLite for local development
        conn = sqlite3.connect('team_dashboard.db', check_same_thread=False)
        
        # Create tables if not exist (SQLite fallback)
        create_tables_sqlite(conn)
        return conn

def create_tables_sqlite(conn):
    """Create SQLite tables if they don't exist"""
    conn.execute('''
    CREATE TABLE IF NOT EXISTS app_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        spatial_target INTEGER DEFAULT 0,
        textual_target INTEGER DEFAULT 0
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS batch_options (
        name TEXT PRIMARY KEY
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS team_members (
        name TEXT PRIMARY KEY,
        team_function TEXT
    )
    ''')
    
    conn.execute('''
    INSERT OR IGNORE INTO app_settings (id, spatial_target, textual_target)
    VALUES (1, 0, 0)
    ''')
    
    # Seed default batches
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM batch_options")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO batch_options (name) VALUES (?)",
            [(b,) for b in DEFAULT_BATCH_OPTIONS]
        )
    
    conn.commit()
def get_app_settings():
    """Load app settings"""
    conn = get_database_connection()
    try:
        df = pd.read_sql_query("SELECT spatial_target, textual_target FROM app_settings WHERE id = 1", conn)
        if df.empty:
            return {'spatial_target': 0, 'textual_target': 0}
        row = df.iloc[0]
        return {'spatial_target': int(row['spatial_target']), 'textual_target': int(row['textual_target'])}
    finally:
        conn.close()

def update_app_settings(spatial_target: int, textual_target: int):
    """Update app settings"""
    conn = get_database_connection()
    cursor = conn.cursor()
    if db_adapter.is_postgres:
        cursor.execute(
            "UPDATE app_settings SET spatial_target = %s, textual_target = %s WHERE id = 1",
            (spatial_target, textual_target)
        )
    else:
        cursor.execute(
            "UPDATE app_settings SET spatial_target = ?, textual_target = ? WHERE id = 1",
            (spatial_target, textual_target)
        )
    conn.commit()
    conn.close()

def load_team_mapping_file():
    """Load team mapping from PM team file (PM.xlsx or PM_team.*)"""
    if os.path.exists('PM.xlsx'):
        df = pd.read_excel('PM.xlsx')
    elif os.path.exists('PM_team.xlsx'):
        df = pd.read_excel('PM_team.xlsx')
    elif os.path.exists('PM_team.csv'):
        df = pd.read_csv('PM_team.csv')
    else:
        return pd.DataFrame()

    df = df.rename(columns={
        'name': 'name',
        'Name': 'name',
        'TEAM FUNCTION': 'team_function',
        'Team Function': 'team_function',
        'team function': 'team_function'
    })

    required_cols = {'name', 'team_function'}
    if not required_cols.issubset(set(df.columns)):
        return pd.DataFrame()

    df['name'] = df['name'].astype(str).str.strip()
    df['team_function'] = df['team_function'].astype(str).str.strip()
    return df

def get_team_members():
    """Get team members from DB, fallback to file and seed DB"""
    conn = get_database_connection()
    try:
        df = pd.read_sql_query("SELECT name, team_function FROM team_members", conn)
    finally:
        conn.close()

    if df.empty:
        file_df = load_team_mapping_file()
        if not file_df.empty:
            for _, row in file_df.iterrows():
                upsert_team_member(row['name'], row['team_function'])
            return file_df
    return df

def upsert_team_member(name: str, team_function: str):
    """Insert or update a team member mapping"""
    conn = get_database_connection()
    cursor = conn.cursor()
    if db_adapter.is_postgres:
        cursor.execute(
            "INSERT INTO team_members (name, team_function) VALUES (%s, %s) "
            "ON CONFLICT(name) DO UPDATE SET team_function = excluded.team_function",
            (name, team_function)
        )
    else:
        cursor.execute(
            "INSERT INTO team_members (name, team_function) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET team_function = excluded.team_function",
            (name, team_function)
        )
    conn.commit()
    conn.close()

def get_batch_options() -> List[str]:
    """Get batch options from DB"""
    conn = get_database_connection()
    try:
        df = pd.read_sql_query("SELECT name FROM batch_options ORDER BY name", conn)
        if df.empty:
            return DEFAULT_BATCH_OPTIONS
        return df['name'].tolist()
    finally:
        conn.close()

def add_batch_option(name: str):
    """Add a batch option"""
    conn = get_database_connection()
    cursor = conn.cursor()
    if db_adapter.is_postgres:
        cursor.execute(
            "INSERT INTO batch_options (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            (name,)
        )
    else:
        cursor.execute("INSERT OR IGNORE INTO batch_options (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

def delete_batch_option(name: str):
    """Delete a batch option"""
    conn = get_database_connection()
    cursor = conn.cursor()
    if db_adapter.is_postgres:
        cursor.execute("DELETE FROM batch_options WHERE name = %s", (name,))
    else:
        cursor.execute("DELETE FROM batch_options WHERE name = ?", (name,))
    conn.commit()
    conn.close()

def main():
    # Initialize database tables for cloud deployment
    if USE_CLOUD_DB:
        try:
            db_adapter.create_tables()
        except Exception as e:
            st.error(f"Database initialization error: {e}")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")

    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    with st.sidebar.expander("Admin Access", expanded=False):
        access_code = st.text_input("Access Code", type="password")
        if access_code:
            st.session_state.is_admin = (access_code == ADMIN_ACCESS_CODE)
        if st.session_state.is_admin:
            st.success("Admin access enabled")
        else:
            st.info("Admin access required for data editing")

    page = st.sidebar.radio(
        "Select Page",
        ["Daily Task Entry", "Data Management", "Configuration"],
        index=0
    )
    
    if page == "Daily Task Entry":
        show_daily_task_entry()
    elif page == "Data Management":
        show_data_management()
    elif page == "Configuration":
        show_configuration()

def show_daily_task_entry():
    """Daily task entry page"""
    # Create two column layout
    col_form, col_preview = st.columns([2, 1])
    
    with col_form:
        batch_options = get_batch_options()
        # Date and user selection outside form for immediate feedback
        submission_date = st.date_input(
            "Date *", 
            value=date.today(),
            help="Select the date for task execution"
        )
        
        # User name selection
        current_users = load_users_from_file()
        user_name = st.selectbox(
            "User Name *",
            options=current_users,
            help="Select the team member"
        )
        
        st.markdown("---")
        st.markdown("**Task Type Selection**")
        
        # Task type selection outside form for immediate response
        col1, col2, col3 = st.columns(3)
        
        with col1:
            spatial_selected = st.checkbox("Spatial")
            textual_selected = st.checkbox("Textual")
        
        with col2:
            qa_selected = st.checkbox("QA")
            qc_selected = st.checkbox("QC")
        
        with col3:
            automation_selected = st.checkbox("Automation")
            other_selected = st.checkbox("Other")
        
        # Initialize variables with defaults
        spatial_completed = spatial_hours = 0
        textual_completed = textual_hours = 0  
        qa_completed = qa_hours = 0
        qc_completed = qc_hours = 0
        automation_completed = automation_hours = 0
        other_completed = other_hours = 0
        overtime_hours = 0.0
        
        spatial_batches = textual_batches = qa_batches = []
        qc_batches = automation_batches = other_batches = []
        
        # Show task details immediately when checkboxes are selected
        if any([spatial_selected, textual_selected, qa_selected, qc_selected, automation_selected, other_selected]):
            st.markdown("---")
            st.markdown("**Task Details**")
            
            # Spatial Tasks
            if spatial_selected:
                st.markdown("**Spatial Tasks**")
                spatial_col1, spatial_col2, spatial_col3 = st.columns([1, 1, 2])
                with spatial_col1:
                    spatial_completed = st.number_input("Spatial Completed *", min_value=1, step=1, value=1, key="spatial_completed")
                with spatial_col2:
                    spatial_hours = st.number_input("Spatial Hours *", min_value=0.1, step=0.1, format="%.2f", value=0.1, key="spatial_hours")
                with spatial_col3:
                    spatial_batches = st.multiselect("Spatial Batches *", options=batch_options, default=[], key="spatial_batches")
            
            # Textual Tasks
            if textual_selected:
                st.markdown("**Textual Tasks**")
                textual_col1, textual_col2, textual_col3 = st.columns([1, 1, 2])
                with textual_col1:
                    textual_completed = st.number_input("Textual Completed *", min_value=1, step=1, value=1, key="textual_completed")
                with textual_col2:
                    textual_hours = st.number_input("Textual Hours *", min_value=0.1, step=0.1, format="%.2f", value=0.1, key="textual_hours")
                with textual_col3:
                    textual_batches = st.multiselect("Textual Batches *", options=batch_options, default=[], key="textual_batches")
            
            # QA Tasks
            if qa_selected:
                st.markdown("**QA Tasks**")
                qa_col1, qa_col2, qa_col3 = st.columns([1, 1, 2])
                with qa_col1:
                    qa_completed = st.number_input("QA Completed *", min_value=1, step=1, value=1, key="qa_completed")
                with qa_col2:
                    qa_hours = st.number_input("QA Hours *", min_value=0.1, step=0.1, format="%.2f", value=0.1, key="qa_hours")
                with qa_col3:
                    qa_batches = st.multiselect("QA Batches *", options=batch_options, default=[], key="qa_batches")
            
            # QC Tasks
            if qc_selected:
                st.markdown("**QC Tasks**")
                qc_col1, qc_col2, qc_col3 = st.columns([1, 1, 2])
                with qc_col1:
                    qc_completed = st.number_input("QC Completed *", min_value=1, step=1, value=1, key="qc_completed")
                with qc_col2:
                    qc_hours = st.number_input("QC Hours *", min_value=0.1, step=0.1, format="%.2f", value=0.1, key="qc_hours")
                with qc_col3:
                    qc_batches = st.multiselect("QC Batches *", options=batch_options, default=[], key="qc_batches")
            
            # Automation Tasks
            if automation_selected:
                st.markdown("**Automation Tasks**")
                automation_col1, automation_col2, automation_col3 = st.columns([1, 1, 2])
                with automation_col1:
                    automation_completed = st.number_input(
                        "Automation Progress % *",
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        value=1.0,
                        format="%.1f",
                        key="automation_completed"
                    )
                with automation_col2:
                    automation_hours = st.number_input("Automation Hours *", min_value=0.1, step=0.1, format="%.2f", value=0.1, key="automation_hours")
                with automation_col3:
                    automation_batches = st.multiselect("Automation Batches *", options=batch_options, default=[], key="automation_batches")
            
            # Other Tasks
            if other_selected:
                st.markdown("**Other Tasks**")
                other_col1, other_col2, other_col3 = st.columns([1, 1, 2])
                with other_col1:
                    other_completed = st.number_input("Other Completed *", min_value=1, step=1, value=1, key="other_completed")
                with other_col2:
                    other_hours = st.number_input("Other Hours *", min_value=0.1, step=0.1, format="%.2f", value=0.1, key="other_hours")
                with other_col3:
                    other_batches = st.multiselect("Other Batches (optional)", options=batch_options, default=[], key="other_batches")

        # Now create form with only summary and submit
        settings = get_app_settings()

        with st.form("daily_task_form", clear_on_submit=False):
            # Calculate total hours
            base_total = (spatial_hours + textual_hours + qa_hours + 
                         qc_hours + automation_hours + other_hours)
            
            # Show hours summary only if tasks are selected
            if any([spatial_selected, textual_selected, qa_selected, qc_selected, automation_selected, other_selected]):
                st.markdown("---")
                st.markdown("**Hours Summary**")
                overtime_hours = st.number_input(
                    "Over Time Hours (optional)",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    value=0.0
                )
                calculated_total = base_total + overtime_hours
                st.metric("Total Hours", f"{calculated_total:.2f} hours")
            
            # Notes
            st.markdown("**Notes**")
            note = st.text_area(
                "Additional Notes", 
                placeholder="Add any relevant notes...",
                height=100
            )
            
            # Submit button
            st.markdown("---")
            submit_col1, submit_col2, submit_col3 = st.columns([1, 2, 1])
            
            with submit_col2:
                submitted = st.form_submit_button(
                    "Submit Task Report", 
                    use_container_width=True,
                    type="primary"
                )
            
            # Form validation and submission
            if submitted:
                # Validate required fields
                errors = []
                if not user_name:
                    errors.append("Please select a user")
                
                # Check if at least one task type is selected
                selected_tasks = [spatial_selected, textual_selected, qa_selected, qc_selected, automation_selected, other_selected]
                if not any(selected_tasks):
                    errors.append("Please select at least one task type")
                
                # Validate selected task types have required fields
                if spatial_selected and (spatial_completed <= 0 or spatial_hours <= 0 or not spatial_batches):
                    errors.append("Spatial task requires completed count > 0, hours > 0, and at least one batch")
                if textual_selected and (textual_completed <= 0 or textual_hours <= 0 or not textual_batches):
                    errors.append("Textual task requires completed count > 0, hours > 0, and at least one batch")
                if qa_selected and (qa_completed <= 0 or qa_hours <= 0 or not qa_batches):
                    errors.append("QA task requires completed count > 0, hours > 0, and at least one batch")
                if qc_selected and (qc_completed <= 0 or qc_hours <= 0 or not qc_batches):
                    errors.append("QC task requires completed count > 0, hours > 0, and at least one batch")
                if automation_selected and (automation_completed <= 0 or automation_hours <= 0 or not automation_batches):
                    errors.append("Automation task requires progress % > 0, hours > 0, and at least one batch")
                if other_selected and (other_completed <= 0 or other_hours <= 0):
                    errors.append("Other task requires completed count > 0 and hours > 0")

                if any(selected_tasks) and calculated_total < 7.5:
                    errors.append("Total hours must be at least 7.5")
                
                if errors:
                    for error in errors:
                        st.error(f"Error: {error}")
                else:
                    # Save data
                    try:
                        save_task_submission({
                            'submission_date': submission_date,
                            'user_names': user_name,
                            'spatial_completed': spatial_completed,
                            'spatial_hours': spatial_hours,
                            'spatial_batches': json.dumps(spatial_batches),
                            'textual_completed': textual_completed,
                            'textual_hours': textual_hours,
                            'textual_batches': json.dumps(textual_batches),
                            'qa_completed': qa_completed,
                            'qa_hours': qa_hours,
                            'qa_batches': json.dumps(qa_batches),
                            'qc_completed': qc_completed,
                            'qc_hours': qc_hours,
                            'qc_batches': json.dumps(qc_batches),
                            'automation_completed': automation_completed,
                            'automation_hours': automation_hours,
                            'automation_batches': json.dumps(automation_batches),
                            'other_completed': other_completed,
                            'other_hours': other_hours,
                            'other_batches': json.dumps(other_batches),
                            'overtime_hours': overtime_hours,
                            'total_hours': calculated_total,
                            'note': note,
                            'submitted_by': user_name
                        })
                        
                        st.success("Task report submitted successfully!")
                        st.cache_data.clear()
                        st.balloons()
                            
                    except Exception as e:
                        st.error(f"Error submitting form: {str(e)}")
    
    with col_preview:
        st.subheader("Today's Summary")
        
        # Show today's submission statistics
        today_stats = get_today_submissions()
        
        if not today_stats.empty:
            # Today's statistics cards
            st.metric("Today's Submissions", len(today_stats))
            
            # Task type distribution
            task_totals = {
                'Spatial': today_stats['spatial_completed'].sum(),
                'Textual': today_stats['textual_completed'].sum(),
                'QA': today_stats['qa_completed'].sum(),
                'QC': today_stats['qc_completed'].sum(),
                'Automation': today_stats['automation_completed'].sum(),
                'Other': today_stats['other_completed'].sum()
            }
            
            # Filter out zero values for pie chart
            non_zero_tasks = {k: v for k, v in task_totals.items() if v > 0}
            
            if non_zero_tasks:
                fig = px.pie(
                    values=list(non_zero_tasks.values()), 
                    names=list(non_zero_tasks.keys()),
                    title="Today's Task Types"
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
            # Recent submissions
            st.markdown("**Recent Submissions:**")
            for _, row in today_stats.tail(3).iterrows():
                try:
                    submit_date = pd.to_datetime(row['submit_time']).strftime("%Y-%m-%d")
                except Exception:
                    submit_date = str(row['submit_time'])[:10]
                st.write(f"• {row['user_names']} - {submit_date}")
        else:
            st.info("No submissions today yet")
            
            # Show weekly goal progress
            st.markdown("**Weekly Goal Progress**")
            weekly_goal = 50  # configurable
            current_week_submissions = get_current_week_submissions()
            progress = min(len(current_week_submissions) / weekly_goal, 1.0)
            
            st.progress(progress)
            st.write(f"{len(current_week_submissions)}/{weekly_goal} submissions this week")

def save_task_submission(data):
    """Save task submission data"""
    conn = get_database_connection()
    cursor = conn.cursor()
    placeholder = "%s" if db_adapter.is_postgres else "?"
    values_placeholder = ", ".join([placeholder] * 24)
    
    cursor.execute(f'''
    INSERT INTO task_submissions 
    (submission_date, user_names, 
     spatial_completed, spatial_hours, spatial_batches,
     textual_completed, textual_hours, textual_batches,
     qa_completed, qa_hours, qa_batches,
     qc_completed, qc_hours, qc_batches,
     automation_completed, automation_hours, automation_batches,
     other_completed, other_hours, other_batches,
    overtime_hours, total_hours, note, submitted_by)
    VALUES ({values_placeholder})
    ''', (
        data['submission_date'],
        data['user_names'],
        data['spatial_completed'],
        data['spatial_hours'],
        data['spatial_batches'],
        data['textual_completed'],
        data['textual_hours'],
        data['textual_batches'],
        data['qa_completed'],
        data['qa_hours'],
        data['qa_batches'],
        data['qc_completed'],
        data['qc_hours'],
        data['qc_batches'],
        data['automation_completed'],
        data['automation_hours'],
        data['automation_batches'],
        data['other_completed'],
        data['other_hours'],
        data['other_batches'],
        data['overtime_hours'],
        data['total_hours'],
        data['note'],
        data['submitted_by']
    ))
    
    conn.commit()
    conn.close()

@st.cache_data(ttl=60)
def get_today_submissions():
    """Get today's submission data"""
    conn = get_database_connection()
    today = date.today()
    placeholder = "%s" if db_adapter.is_postgres else "?"
    query = f'''
    SELECT * FROM task_submissions 
    WHERE submission_date = {placeholder} 
    ORDER BY submit_time DESC
    '''
    try:
        df = pd.read_sql_query(query, conn, params=[today])
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

@st.cache_data(ttl=120)
def get_current_week_submissions():
    """Get current week submission data"""
    conn = get_database_connection()
    # Get start of week (Monday)
    today = date.today()
    start_of_week = today - pd.Timedelta(days=today.weekday())
    
    placeholder = "%s" if db_adapter.is_postgres else "?"
    query = f'''
    SELECT * FROM task_submissions 
    WHERE submission_date >= {placeholder} 
    ORDER BY submit_time DESC
    '''
    try:
        df = pd.read_sql_query(query, conn, params=[start_of_week])
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def show_performance_overview():
    """Performance overview page"""
    st.header("Performance Overview")
    
    # Date range selection
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        start_date = st.date_input("Start Date", value=date.today() - pd.Timedelta(days=7))
    with col2:
        end_date = st.date_input("End Date", value=date.today())
    with col3:
        st.write("")  # empty space
        if st.button("Refresh Data", use_container_width=True):
            st.rerun()
    
    # Get data
    df = get_submissions_in_range(start_date, end_date)
    
    if not df.empty:
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_submissions = len(df)
            st.metric("Total Submissions", total_submissions)
        
        with col2:
            unique_users = df['user_names'].nunique()
            st.metric("Active Users", unique_users)
        
        with col3:
            total_tasks = (df['spatial_completed'] + df['textual_completed'] + 
                          df['qa_completed'] + df['qc_completed'] + 
                          df['automation_completed'] + df['other_completed']).sum()
            st.metric("Total Tasks Completed", f"{total_tasks:,}")
        
        with col4:
            total_hours = df['total_hours'].sum()
            st.metric("Total Hours", f"{total_hours:.1f}")
        
        # Visualization charts
        tab1, tab2, tab3 = st.tabs(["Trends", "Team Performance", "Batch Analysis"])
        
        with tab1:
            show_trend_charts(df)
        
        with tab2:
            show_team_performance(df)
        
        with tab3:
            show_batch_analysis(df)
            
    else:
        st.info("No data available for the selected date range")

@st.cache_data(ttl=300)
def get_submissions_in_range(start_date, end_date):
    """Get submissions within date range"""
    conn = get_database_connection()
    placeholder = "%s" if db_adapter.is_postgres else "?"
    query = f'''
    SELECT * FROM task_submissions 
    WHERE submission_date BETWEEN {placeholder} AND {placeholder}
    ORDER BY submission_date DESC
    '''
    try:
        df = pd.read_sql_query(query, conn, params=[start_date, end_date])
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def show_trend_charts(df):
    """Show trend charts"""
    # Aggregate data by date
    daily_stats = df.groupby('submission_date').agg({
        'spatial_completed': 'sum',
        'textual_completed': 'sum',
        'qa_completed': 'sum',
        'qc_completed': 'sum',
        'automation_completed': 'sum',
        'other_completed': 'sum',
        'total_hours': 'sum',
        'id': 'count'  # submission count
    }).reset_index()
    daily_stats.rename(columns={'id': 'submissions_count'}, inplace=True)
    
    # Task completion trends
    fig1 = go.Figure()
    
    task_types = ['spatial_completed', 'textual_completed', 'qa_completed', 
                  'qc_completed', 'automation_completed', 'other_completed']
    colors = ['blue', 'green', 'red', 'orange', 'purple', 'brown']
    
    for i, task_type in enumerate(task_types):
        fig1.add_trace(go.Scatter(
            x=daily_stats['submission_date'], 
            y=daily_stats[task_type],
            mode='lines+markers', 
            name=task_type.replace('_completed', '').capitalize(),
            line=dict(color=colors[i])
        ))
    
    fig1.update_layout(
        title="Daily Task Completion Trends",
        xaxis_title="Date",
        yaxis_title="Tasks Completed",
        height=400
    )
    
    st.plotly_chart(fig1, use_container_width=True)
    
    # Hours trend
    fig2 = px.line(daily_stats, x='submission_date', y='total_hours',
                   title="Daily Hours Worked",
                   labels={'total_hours': 'Hours', 'submission_date': 'Date'})
    fig2.update_layout(height=400)
    st.plotly_chart(fig2, use_container_width=True)

def show_team_performance(df):
    """Show team performance"""
    # User performance
    user_performance = df.groupby('user_names').agg({
        'spatial_completed': 'sum',
        'textual_completed': 'sum',
        'qa_completed': 'sum',
        'qc_completed': 'sum',
        'automation_completed': 'sum',
        'other_completed': 'sum',
        'total_hours': 'sum'
    }).round(2)
    
    user_performance['total_tasks'] = (user_performance['spatial_completed'] + 
                                      user_performance['textual_completed'] + 
                                      user_performance['qa_completed'] + 
                                      user_performance['qc_completed'] + 
                                      user_performance['automation_completed'] + 
                                      user_performance['other_completed'])
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(user_performance.reset_index(), x='user_name', y='total_tasks',
                    title="Total Tasks by User")
        fig.update_xaxes(tickangle=45)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(user_performance.reset_index(), x='user_name', y='total_hours',
                    title="Total Hours by User")
        fig.update_xaxes(tickangle=45)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Detailed table
    st.subheader("Detailed User Performance")
    user_performance['efficiency_ratio'] = user_performance['total_tasks'] / (user_performance['total_hours'] + 0.01)
    user_performance = user_performance.round(2)
    st.dataframe(user_performance, use_container_width=True)

def show_batch_analysis(df):
    """Show batch analysis"""
    # Parse batch data
    batch_data = []
    
    task_types = ['spatial', 'textual', 'qa', 'qc', 'automation', 'other']
    
    for _, row in df.iterrows():
        for task_type in task_types:
            batch_col = f'{task_type}_batches'
            completed_col = f'{task_type}_completed'
            hours_col = f'{task_type}_hours'
            
            if row[batch_col]:
                try:
                    batches = json.loads(row[batch_col])
                    for batch in batches:
                        batch_data.append({
                            'batch': batch,
                            'task_type': task_type.capitalize(),
                            'date': row['submission_date'],
                            'user': row['user_names'],
                            'completed': row[completed_col],
                            'hours': row[hours_col]
                        })
                except (json.JSONDecodeError, TypeError):
                    continue
    
    if batch_data:
        batch_df = pd.DataFrame(batch_data)
        
        # Batch statistics
        batch_stats = batch_df.groupby('batch').agg({
            'completed': 'sum',
            'hours': 'sum'
        }).round(2)
        batch_stats = batch_stats.sort_values('completed', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(batch_stats.reset_index(), values='completed', names='batch',
                        title="Tasks Distribution by Batch")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(batch_stats.reset_index(), x='batch', y='hours',
                        title="Total Hours by Batch")
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        
        # Batch details table
        st.subheader("Batch Performance Details")
        st.dataframe(batch_stats, use_container_width=True)
        
        # Task type by batch
        st.subheader("Task Types by Batch")
        batch_task_pivot = batch_df.pivot_table(
            index='batch', 
            columns='task_type', 
            values='completed', 
            aggfunc='sum', 
            fill_value=0
        )
        st.dataframe(batch_task_pivot, use_container_width=True)

def show_data_management():
    """Data management page"""
    st.header("Data Management")

    if st.session_state.get("is_admin", False):
        tab1, tab2, tab3, tab4 = st.tabs(["View All Data", "Edit Records", "Export Data", "Data Cleanup"])
    else:
        tab1 = st.tabs(["View All Data"])[0]
        st.info("Admin access is required for Edit Records, Export Data, and Data Cleanup.")

    with tab1:
        st.subheader("All Task Submissions")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_filter = st.date_input("Filter by Date", value=None)
        with col2:
            user_filter = st.selectbox("Filter by User", ["All Users"] + load_users_from_file())
        with col3:
            if st.button("Apply Filters"):
                pass
        
        # Apply filters
        df = get_all_submissions()
        
        if date_filter:
            df = df[pd.to_datetime(df['submission_date']).dt.date == date_filter]
        
        if user_filter != "All Users":
            df = df[df['user_names'] == user_filter]
        
        # Display data
        if not df.empty:
            st.dataframe(df, use_container_width=True, height=400)
            st.write(f"Showing {len(df)} records")
        else:
            st.info("No data matches the current filters")
    
    if st.session_state.get("is_admin", False):
        with tab2:
            st.subheader("Edit Task Records")
            
            df = get_all_submissions()
            if not df.empty:
                # Select record to edit
                selected_id = st.selectbox("Select Record to Edit", df['id'].tolist(), 
                                         format_func=lambda x: f"ID {x} - {df[df['id']==x]['user_names'].iloc[0]} - {df[df['id']==x]['submission_date'].iloc[0]}")
                
                if selected_id:
                    record = df[df['id'] == selected_id].iloc[0]
                    
                    # Edit form
                    with st.form(f"edit_form_{selected_id}"):
                        st.write(f"Editing Record ID: {selected_id}")
                        
                        new_date = st.date_input("Date", value=pd.to_datetime(record['submission_date']).date())
                        new_note = st.text_area("Note", value=record['note'] or "")
                        
                        if st.form_submit_button("Update Record"):
                            update_record(selected_id, new_date, new_note)
                            st.success("Record updated successfully!")
                            st.rerun()
            else:
                st.info("No records to edit")

        with tab3:
            st.subheader("Export Data")
            
            export_format = st.radio("Export Format", ["Excel", "CSV", "JSON"])
            
            col1, col2 = st.columns(2)
            with col1:
                export_start_date = st.date_input("Export Start Date", value=date.today()-pd.Timedelta(days=30))
            with col2:
                export_end_date = st.date_input("Export End Date", value=date.today())
            
            if st.button("Export Data"):
                df = get_submissions_in_range(export_start_date, export_end_date)
                df = _prepare_export_df(df)
                
                if export_format == "Excel":
                    output = create_excel_export(df)
                    st.download_button(
                        "Download Excel",
                        output,
                        f"task_submissions_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                elif export_format == "CSV":
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "Download CSV",
                        csv,
                        f"task_submissions_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )
                else:  # JSON
                    json_data = df.to_json(orient='records', indent=2)
                    st.download_button(
                        "Download JSON",
                        json_data,
                        f"task_submissions_{datetime.now().strftime('%Y%m%d')}.json",
                        "application/json"
                    )
    
        with tab4:
            st.subheader("Data Cleanup")
            st.warning("Use these options carefully. Deleted data cannot be recovered.")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Delete Old Records (>90 days)", type="secondary"):
                    if st.session_state.get('confirm_delete', False):
                        delete_old_records(90)
                        st.success("Old records deleted")
                        del st.session_state.confirm_delete
                    else:
                        st.session_state.confirm_delete = True
                        st.warning("Click again to confirm deletion")
            
            with col2:
                if st.button("Reset All Data", type="secondary"):
                    if st.session_state.get('confirm_reset', False):
                        reset_all_data()
                        st.success("All data reset")
                        del st.session_state.confirm_reset
                    else:
                        st.session_state.confirm_reset = True
                        st.warning("Click again to confirm reset")


@st.cache_data(ttl=120)
def get_all_submissions():
    """Get all submission data"""
    conn = get_database_connection()
    query = "SELECT * FROM task_submissions ORDER BY submit_time DESC"
    try:
        df = pd.read_sql_query(query, conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def update_record(record_id, new_date, new_note):
    """Update record"""
    conn = get_database_connection()
    cursor = conn.cursor()
    if db_adapter.is_postgres:
        cursor.execute(
            "UPDATE task_submissions SET submission_date = %s, note = %s WHERE id = %s",
            (new_date, new_note, record_id)
        )
    else:
        cursor.execute(
            "UPDATE task_submissions SET submission_date = ?, note = ? WHERE id = ?",
            (new_date, new_note, record_id)
        )
    conn.commit()
    conn.close()

def delete_old_records(days):
    """Delete old records"""
    conn = get_database_connection()
    cursor = conn.cursor()
    cutoff_date = date.today() - pd.Timedelta(days=days)
    if db_adapter.is_postgres:
        cursor.execute(
            "DELETE FROM task_submissions WHERE submission_date < %s",
            (cutoff_date,)
        )
    else:
        cursor.execute(
            "DELETE FROM task_submissions WHERE submission_date < ?",
            (cutoff_date,)
        )
    conn.commit()
    conn.close()

def reset_all_data():
    """Reset all data"""
    conn = get_database_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM task_submissions")
    conn.commit()
    conn.close()

def _format_batch_list(value):
    """Format batch list values for export display"""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join([str(v) for v in value])
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return ", ".join([str(v) for v in parsed])
        except Exception:
            return value
        return value
    return str(value)

def _prepare_export_df(df):
    """Prepare dataframe for export (normalize batch list columns)."""
    export_df = df.copy()
    batch_cols = [
        'spatial_batches', 'textual_batches', 'qa_batches',
        'qc_batches', 'automation_batches', 'other_batches'
    ]
    for col in batch_cols:
        if col in export_df.columns:
            export_df[col] = export_df[col].apply(_format_batch_list)
    return export_df

def create_excel_export(df):
    """Create Excel export file"""
    export_df = _prepare_export_df(df)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, sheet_name='Task Submissions', index=False)
        
        # Add summary sheet
        if not export_df.empty:
            summary_data = {
                'Total Submissions': [len(export_df)],
                'Total Tasks': [(export_df['spatial_completed'] + export_df['textual_completed'] + 
                               export_df['qa_completed'] + export_df['qc_completed'] + 
                               export_df['automation_completed'] + export_df['other_completed']).sum()],
                'Total Hours': [export_df['total_hours'].sum()],
                'Date Range': [f"{export_df['submission_date'].min()} to {export_df['submission_date'].max()}"],
                'Unique Users': [export_df['user_names'].nunique()]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    return output.getvalue()

def show_analytics():
    """Analytics page"""
    st.header("Analytics")
    
    # Get data
    df = get_all_submissions()
    
    if not df.empty:
        tab1, tab2, tab3 = st.tabs(["KPI Dashboard", "Productivity Analysis", "Forecasting"])
        
        with tab1:
            show_kpi_dashboard(df)
        
        with tab2:
            show_productivity_analysis(df)
        
        with tab3:
            show_forecasting(df)
    else:
        st.info("Not enough data for advanced analytics")

def show_kpi_dashboard(df):
    """KPI dashboard"""
    st.subheader("Key Performance Indicators")
    
    # Calculate KPIs
    total_tasks = (df['spatial_completed'] + df['textual_completed'] + 
                  df['qa_completed'] + df['qc_completed'] + 
                  df['automation_completed'] + df['other_completed']).sum()
    total_hours = df['total_hours'].sum()
    
    # KPI cards
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        st.metric(
            "Overall Efficiency", 
            f"{total_tasks / (total_hours + 0.01):.1f}",
            help="Tasks completed per hour"
        )
    
    with kpi_col2:
        automation_ratio = df['automation_completed'].sum() / (total_tasks + 0.01) * 100
        st.metric("Automation Ratio", f"{automation_ratio:.1f}%")
    
    with kpi_col3:
        avg_daily_tasks = total_tasks / max(len(df['submission_date'].unique()), 1)
        st.metric("Avg Daily Tasks", f"{avg_daily_tasks:.1f}")
    
    with kpi_col4:
        unique_users = df['user_names'].nunique()
        st.metric("Active Users", unique_users)
    
    # KPI trends
    daily_kpis = df.groupby('submission_date').agg({
        'spatial_completed': 'sum',
        'textual_completed': 'sum',
        'qa_completed': 'sum',
        'qc_completed': 'sum',
        'automation_completed': 'sum',
        'other_completed': 'sum',
        'total_hours': 'sum'
    })
    
    daily_kpis['total_tasks'] = (daily_kpis['spatial_completed'] + daily_kpis['textual_completed'] + 
                                daily_kpis['qa_completed'] + daily_kpis['qc_completed'] + 
                                daily_kpis['automation_completed'] + daily_kpis['other_completed'])
    daily_kpis['efficiency'] = daily_kpis['total_tasks'] / (daily_kpis['total_hours'] + 0.01)
    
    fig = px.line(daily_kpis.reset_index(), x='submission_date', y='efficiency',
                 title="Daily Efficiency Trend")
    st.plotly_chart(fig, use_container_width=True)

def show_productivity_analysis(df):
    """Productivity analysis"""
    st.subheader("Productivity Analysis")
    
    # Weekday vs weekend analysis
    df['day_of_week'] = pd.to_datetime(df['submission_date']).dt.day_name()
    df['is_weekend'] = pd.to_datetime(df['submission_date']).dt.weekday >= 5
    
    df['total_tasks'] = (df['spatial_completed'] + df['textual_completed'] + 
                        df['qa_completed'] + df['qc_completed'] + 
                        df['automation_completed'] + df['other_completed'])
    
    col1, col2 = st.columns(2)
    
    with col1:
        weekday_stats = df.groupby('day_of_week').agg({
            'total_tasks': 'sum'
        })
        
        # Reorder weekdays
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_stats = weekday_stats.reindex([day for day in day_order if day in weekday_stats.index])
        
        fig = px.bar(weekday_stats.reset_index(), x='day_of_week', y='total_tasks',
                    title="Tasks by Day of Week")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        weekend_comparison = df.groupby('is_weekend').agg({
            'total_tasks': 'mean',
            'total_hours': 'mean'
        })
        weekend_comparison.index = ['Weekday', 'Weekend']
        
        st.write("**Average per Submission:**")
        st.dataframe(weekend_comparison.round(2))

def show_forecasting(df):
    """Forecasting analysis"""
    st.subheader("Performance Forecasting")
    
    # Simple trend forecasting
    df['total_tasks'] = (df['spatial_completed'] + df['textual_completed'] + 
                        df['qa_completed'] + df['qc_completed'] + 
                        df['automation_completed'] + df['other_completed'])
    
    daily_totals = df.groupby('submission_date').agg({
        'total_tasks': 'sum',
        'total_hours': 'sum'
    }).reset_index()
    
    if len(daily_totals) >= 7:  # Need at least a week of data
        daily_totals['date_num'] = pd.to_datetime(daily_totals['submission_date']).astype(int) // 10**9 // 86400
        
        # Simple linear regression
        from sklearn.linear_model import LinearRegression
        import numpy as np
        
        X = daily_totals['date_num'].values.reshape(-1, 1)
        y = daily_totals['total_tasks'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Predict next 7 days
        future_days = 7
        last_date_num = daily_totals['date_num'].max()
        future_dates_num = np.array([last_date_num + i for i in range(1, future_days + 1)]).reshape(-1, 1)
        future_predictions = model.predict(future_dates_num)
        
        # Create forecast chart
        fig = go.Figure()
        
        # Historical data
        fig.add_trace(go.Scatter(
            x=daily_totals['submission_date'],
            y=daily_totals['total_tasks'],
            mode='lines+markers',
            name='Historical Data',
            line=dict(color='blue')
        ))
        
        # Forecast data
        future_dates = [pd.to_datetime(daily_totals['submission_date'].max()) + pd.Timedelta(days=i) 
                       for i in range(1, future_days + 1)]
        
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=future_predictions,
            mode='lines+markers',
            name='Forecast',
            line=dict(color='red', dash='dash')
        ))
        
        fig.update_layout(
            title="7-Day Task Completion Forecast",
            xaxis_title="Date",
            yaxis_title="Total Tasks",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show forecast statistics
        col1, col2 = st.columns(2)
        with col1:
            avg_historical = daily_totals['total_tasks'].mean()
            st.metric("Historical Daily Average", f"{avg_historical:.1f}")
        
        with col2:
            avg_forecast = future_predictions.mean()
            change = ((avg_forecast - avg_historical) / avg_historical) * 100
            st.metric("Forecast Daily Average", f"{avg_forecast:.1f}", f"{change:+.1f}%")
    else:
        st.info("Need at least 7 days of data for forecasting")

def show_configuration():
    """Configuration page for updating users and batches"""
    st.header("Configuration")
    
    tab1, tab2, tab3 = st.tabs(["User Management", "Batch Management", "System Settings"])
    
    with tab1:
        st.subheader("User Management")
        
        current_users = load_users_from_file()
        team_df = get_team_members()
        team_map = {}
        if not team_df.empty:
            team_map = dict(zip(team_df['name'], team_df['team_function']))
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.info("Current Users:")
            user_rows = [
                {"Name": user, "Team Function": team_map.get(user, "")}
                for user in current_users
            ]
            st.dataframe(pd.DataFrame(user_rows), use_container_width=True, height=260)
        
        with col2:
            st.markdown("**Actions:**")
            if st.button("Refresh User List"):
                st.rerun()
        
        st.markdown("---")
        st.markdown("**Add New User:**")
        with st.form("add_user_form"):
            new_user = st.text_input("User Name")
            if st.session_state.get("is_admin", False):
                existing_teams = sorted({v for v in team_map.values() if v})
                team_function = st.selectbox(
                    "Team Function",
                    options=[""] + existing_teams,
                    help="Select an existing team or leave blank to type a new one"
                )
                if team_function == "":
                    team_function = st.text_input("Or enter new Team Function")
            if st.form_submit_button("Add User"):
                if new_user and new_user not in current_users:
                    current_users.append(new_user)
                    if save_users_to_file(current_users):
                        if st.session_state.get("is_admin", False):
                            upsert_team_member(new_user, (team_function or "").strip())
                        st.success(f"User '{new_user}' added successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to save user list")
                else:
                    st.error("User name already exists or is empty")
        
        st.markdown("**Remove User:**")
        if current_users:
            with st.form("remove_user_form"):
                user_to_remove = st.selectbox("Select user to remove", current_users)
                if st.form_submit_button("Remove User"):
                    current_users.remove(user_to_remove)
                    if save_users_to_file(current_users):
                        st.success(f"User '{user_to_remove}' removed successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to save user list")

        st.markdown("---")
        st.markdown("**Edit Team Function (Admin Only):**")
        if st.session_state.get("is_admin", False):
            if current_users:
                with st.form("edit_team_function_form"):
                    selected_user = st.selectbox("User", current_users, key="team_user_select")
                    current_team = team_map.get(selected_user, "")
                    new_team = st.text_input("Team Function", value=current_team)
                    if st.form_submit_button("Save Team Function"):
                        upsert_team_member(selected_user, new_team.strip())
                        st.success("Team function updated")
                        st.rerun()
        else:
            st.info("Admin access required to edit team functions")
    
    with tab2:
        st.subheader("Batch Management")

        current_batches = get_batch_options()
        st.info("Current Batches:")
        for i, batch in enumerate(current_batches):
            st.write(f"{i+1}. {batch}")

        st.markdown("---")
        if st.session_state.get("is_admin", False):
            with st.form("add_batch_form"):
                new_batch = st.text_input("Add Batch")
                if st.form_submit_button("Add Batch"):
                    if new_batch.strip():
                        add_batch_option(new_batch.strip())
                        st.success("Batch added")
                        st.rerun()

            if current_batches:
                batch_to_delete = st.selectbox("Delete Batch", current_batches)
                if st.button("Delete Selected Batch"):
                    delete_batch_option(batch_to_delete)
                    st.success("Batch deleted")
                    st.rerun()
        else:
            st.info("Admin access required to modify batches")
    
    with tab3:
        st.subheader("System Settings")
        
        st.markdown("---")
        st.markdown("**Database Info:**")
        try:
            df = get_all_submissions()
            st.write(f"Total Records: {len(df)}")
            if not df.empty:
                st.write(f"Date Range: {df['submission_date'].min()} to {df['submission_date'].max()}")
                
                # Calculate database size
                import os
                if os.path.exists('team_dashboard.db'):
                    size_bytes = os.path.getsize('team_dashboard.db')
                    size_mb = size_bytes / (1024 * 1024)
                    st.write(f"Database Size: {size_mb:.2f} MB")
                
        except:
            st.write("Database: Empty or not accessible")
        
        st.markdown("---")
        st.subheader("Team Function (Admin Only)")
        if st.session_state.get("is_admin", False):
            current_users = load_users_from_file()
            team_df = get_team_members()
            with st.form("team_function_form"):
                selected_user = st.selectbox("User", current_users)
                existing = team_df[team_df['name'] == selected_user]
                current_team = existing['team_function'].iloc[0] if not existing.empty else ""
                team_function = st.text_input("Team Function", value=current_team)
                if st.form_submit_button("Save Team Function"):
                    upsert_team_member(selected_user, team_function.strip())
                    st.success("Team function updated")
                    st.rerun()
        else:
            st.info("Admin access required to edit team functions")

        st.markdown("---")
        st.markdown("**File Locations:**")
        st.write("- Application: team_dashboard.py")
        if db_adapter.is_postgres:
            st.write("- Database: Supabase (cloud)")
        else:
            st.write("- Database: team_dashboard.db")
        if os.path.exists('PM.xlsx'):
            st.write("- User List: PM.xlsx")
        else:
            st.write("- User List: PM_users.txt")
        
        if st.button("Export Current Configuration"):
            config_data = {
                'users': load_users_from_file(),
                'batches': get_batch_options(),
                'export_date': datetime.now().isoformat()
            }
            config_json = json.dumps(config_data, indent=2)
            st.download_button(
                "Download Configuration",
                config_json,
                f"dashboard_config_{datetime.now().strftime('%Y%m%d')}.json",
                "application/json"
            )

if __name__ == "__main__":
    # Initialize database
    get_database_connection()
    main()