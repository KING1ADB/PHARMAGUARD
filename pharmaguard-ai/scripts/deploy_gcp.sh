#!/usr/bin/env bash
# ==============================================================================
# PharmaGuard AI — Automated Google Cloud Production Deployment Script
# ==============================================================================
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-pharmaguard-ai-prod}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE_NAME="pharmaguard-backend"
GAR_REPO="pharmaguard-repo"
IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/$GAR_REPO/pharmaguard-backend:latest"

echo "===================================================================="
echo "🚀 Starting PharmaGuard AI Google Cloud Production Deployment"
echo "Project: $PROJECT_ID | Region: $REGION"
echo "===================================================================="

# 1. Verify gcloud authentication & configuration
echo "🔍 Checking GCP authentication..."
gcloud config set project "$PROJECT_ID"

# 2. Build & Push Docker Image
echo "📦 Building production container image..."
docker build -t "$IMAGE_TAG" -f Dockerfile .

echo "📤 Pushing image to Google Artifact Registry..."
gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
docker push "$IMAGE_TAG"

# 3. Deploy to Google Cloud Run
echo "🚀 Deploying to Cloud Run service: $SERVICE_NAME..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE_TAG" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 20 \
  --cpu 2 \
  --memory 4Gi \
  --concurrency 80 \
  --timeout 300 \
  --set-env-vars APP_ENV=production,LOG_LEVEL=INFO,ENABLE_SIMULATION_FEATURES=false,USE_LOCAL_STORAGE_FALLBACK=false

# 4. Fetch Deployed URL & Run Verification Smoke Tests
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --format='value(status.url)')
echo "🌐 Service successfully deployed to: $SERVICE_URL"

echo "🧪 Running Automated Production Deployment Verification..."
python scripts/verify_gcp_deployment.py --url "$SERVICE_URL"

echo "===================================================================="
echo "✅ PharmaGuard AI Google Cloud Deployment Completed Successfully!"
echo "===================================================================="
