FROM python:3.11-slim

WORKDIR /app

# Set env var to fix macOS/OpenMP XGBoost conflict
ENV KMP_DUPLICATE_LIB_OK="TRUE"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the fastembed model during the Docker build phase
# This prevents network timeouts on Render's free tier runtime environment
RUN python -c "from langchain_community.embeddings.fastembed import FastEmbedEmbeddings; FastEmbedEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2', threads=1)"

# Copy project files
COPY . .

# We'll override the command in docker-compose for each service
CMD ["bash"]
