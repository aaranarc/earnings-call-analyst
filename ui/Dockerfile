FROM python:3.11-slim
WORKDIR /app
COPY ui/requirements.txt ui/requirements.txt
RUN pip install --no-cache-dir -r ui/requirements.txt
COPY streamlit_app.py .
COPY ui/ ui/
COPY .streamlit/config.toml .streamlit/config.toml
RUN useradd --create-home analyst && chown -R analyst:analyst /app
USER analyst
EXPOSE 8501
CMD ["sh", "-c", "exec streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
