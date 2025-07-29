FROM apache/airflow:3.0.3-python3.10

# Only install what's absolutely necessary that's NOT in the base image
COPY requirements.txt /
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt

# Create necessary directories
USER root
RUN mkdir -p /opt/dbt /opt/data
USER airflow

# Copy configuration and source code
COPY dbt_project /opt/dbt_project
COPY config/profiles.yml /opt/dbt/profiles.yml
COPY --chown=airflow:root ./src /opt/airflow/src
COPY --chown=airflow:root ./airflow/dags /opt/airflow/dags

# Set environment variables
ENV DBT_PROFILES_DIR=/opt/dbt
ENV DBT_PROJECT_DIR=/opt/dbt_project