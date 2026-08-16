#!/bin/bash
# Install dependencies
pip install -r requirements.txt

# Pre-download the FastEmbed model to the local cache during the build phase.
# This prevents the app from hanging during runtime if Render's free tier runtime 
# network blocks or throttles connections to HuggingFace.
echo "Pre-downloading FastEmbed model..."
python -c "from langchain_community.embeddings.fastembed import FastEmbedEmbeddings; FastEmbedEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2', threads=1)"
echo "Build complete!"
