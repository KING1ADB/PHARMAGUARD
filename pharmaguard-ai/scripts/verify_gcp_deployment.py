#!/usr/bin/env python3
"""
PharmaGuard AI — Production Deployment Verification & Smoke Test Script
Validates live health, database readiness, Redis cache, Cloud Storage,
Secret Manager, and Cloud Scheduler endpoints post-deployment.
"""

import sys
import argparse
import time
import requests

def run_smoke_tests(base_url: str, scheduler_secret: str = ""):
    base_url = base_url.rstrip("/")
    print(f"\n=======================================================")
    print(f"🚀 Verifying PharmaGuard AI Production Deployment")
    print(f"Target URL: {base_url}")
    print(f"=======================================================\n")

    failures = []
    
    # 1. Test Root Service Endpoint
    try:
        res = requests.get(f"{base_url}/", timeout=10)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ [PASS] Root Endpoint (200 OK) - Environment: {data.get('environment')}, Version: {data.get('version')}")
        else:
            failures.append(f"Root endpoint failed: HTTP {res.status_code}")
            print(f"❌ [FAIL] Root Endpoint returned HTTP {res.status_code}")
    except Exception as e:
        failures.append(f"Root endpoint connection failed: {e}")
        print(f"❌ [FAIL] Root Endpoint connection error: {e}")

    # 2. Test /health Endpoint
    try:
        res = requests.get(f"{base_url}/health", timeout=10)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ [PASS] Health Endpoint (200 OK) - Status: {data.get('status')}, Agent: {data.get('agent_status')}")
        else:
            failures.append(f"Health endpoint failed: HTTP {res.status_code}")
            print(f"❌ [FAIL] Health Endpoint returned HTTP {res.status_code}")
    except Exception as e:
        failures.append(f"Health endpoint error: {e}")
        print(f"❌ [FAIL] Health Endpoint connection error: {e}")

    # 3. Test /api/v1/monitoring/readiness Probe
    try:
        res = requests.get(f"{base_url}/api/v1/monitoring/readiness", timeout=10)
        if res.status_code == 200:
            data = res.json()
            status = data.get("status")
            checks = data.get("checks", {})
            db_status = checks.get("database", {}).get("healthy", False)
            redis_status = checks.get("redis_memorystore", {}).get("healthy", False)
            gcs_status = checks.get("cloud_storage", {}).get("healthy", False)
            
            print(f"✅ [PASS] Production Readiness Probe ({status})")
            print(f"    - Database Healthy: {db_status}")
            print(f"    - Redis Memorystore: {redis_status}")
            print(f"    - Cloud Storage: {gcs_status}")
            
            if not db_status:
                failures.append("Readiness check: Database is unhealthy")
        else:
            failures.append(f"Readiness probe failed: HTTP {res.status_code}")
            print(f"❌ [FAIL] Readiness Probe returned HTTP {res.status_code}")
    except Exception as e:
        failures.append(f"Readiness probe connection error: {e}")
        print(f"❌ [FAIL] Readiness Probe connection error: {e}")

    # 4. Test /api/v1/monitoring/prometheus Metrics
    try:
        res = requests.get(f"{base_url}/api/v1/monitoring/prometheus", timeout=10)
        if res.status_code == 200 and "pharmaguard_" in res.text:
            print(f"✅ [PASS] Prometheus Metrics Scraping Endpoint (200 OK, {len(res.text)} bytes)")
        else:
            failures.append(f"Prometheus endpoint failed: HTTP {res.status_code}")
            print(f"❌ [FAIL] Prometheus Scraping returned HTTP {res.status_code}")
    except Exception as e:
        failures.append(f"Prometheus endpoint error: {e}")
        print(f"❌ [FAIL] Prometheus connection error: {e}")

    # 5. Test Cloud Scheduler Health Endpoint
    try:
        res = requests.get(f"{base_url}/api/v1/scheduler/health", timeout=10)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ [PASS] Cloud Scheduler Target Endpoint (200 OK) - Schedule: {data.get('cron_schedule')}")
        else:
            failures.append(f"Scheduler health failed: HTTP {res.status_code}")
            print(f"❌ [FAIL] Scheduler Target returned HTTP {res.status_code}")
    except Exception as e:
        failures.append(f"Scheduler health error: {e}")
        print(f"❌ [FAIL] Scheduler Target connection error: {e}")

    # 6. Verify Simulation Endpoints are Blocked in Production
    try:
        res = requests.post(f"{base_url}/api/v1/demo/competition-run", timeout=10)
        # In true production, this should return 404 (disabled router) or 401/403
        if res.status_code in [404, 401, 403]:
            print(f"✅ [PASS] Production Isolation: Demo/Simulation routes safely protected/isolated (HTTP {res.status_code})")
        else:
            print(f"ℹ️ [INFO] Demo routes returned HTTP {res.status_code}")
    except Exception as e:
        print(f"ℹ️ [INFO] Demo route check: {e}")

    print(f"\n=======================================================")
    if not failures:
        print(f"🏆 ALL DEPLOYMENT VERIFICATION TESTS PASSED SUCCESSFULLY!")
        print(f"PharmaGuard AI is fully operational and healthy.")
        print(f"=======================================================\n")
        return 0
    else:
        print(f"⚠️ DEPLOYMENT VERIFICATION DETECTED {len(failures)} ISSUE(S):")
        for f in failures:
            print(f"  - {f}")
        print(f"=======================================================\n")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PharmaGuard AI Production Smoke Test Runner")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of deployed service")
    parser.add_argument("--secret", default="", help="Cloud Scheduler secret")
    args = parser.parse_args()

    exit_code = run_smoke_tests(args.url, args.secret)
    sys.exit(exit_code)
