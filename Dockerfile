FROM python:3.11-slim

WORKDIR /app

# Set env var to fix macOS/OpenMP XGBoost conflict
ENV KMP_DUPLICATE_LIB_OK="TRUE"

# Prevent ML libraries from spin-locking and hanging on Render's restricted CPUs
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV ONNXRUNTIME_NUM_THREADS=1
ENV RAYON_NUM_THREADS=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the fastembed model during the Docker build phase
# We explicitly set cache_dir to ensure it is saved in the working directory and not lost in a hidden root folder
RUN python -c "from langchain_community.embeddings.fastembed import FastEmbedEmbeddings; FastEmbedEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2', threads=1, cache_dir='/app/models/fastembed_cache')"

# Copy project files
COPY . .

# We'll override the command in docker-compose for each service
CMD ["bash"]

ENV HF_HUB_OFFLINE=1
