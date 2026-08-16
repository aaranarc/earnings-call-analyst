FROM python:3.11-slim

WORKDIR /app

# Set env var to fix macOS/OpenMP XGBoost conflict
ENV KMP_DUPLICATE_LIB_OK="TRUE"

# We are using Gemini Cloud API, so no local thread limits are necessary

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Using Gemini API for Embeddings, no local models to download

# Copy project files
COPY . .

# We'll override the command in docker-compose for each service
CMD ["bash"]

