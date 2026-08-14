FROM python:3.11-slim

WORKDIR /app

# Set env var to fix macOS/OpenMP XGBoost conflict
ENV KMP_DUPLICATE_LIB_OK="TRUE"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# We'll override the command in docker-compose for each service
CMD ["bash"]
