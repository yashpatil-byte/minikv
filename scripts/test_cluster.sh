#!/bin/bash
# Test the distributed cluster with basic operations
# Usage: ./scripts/test_cluster.sh

set -e

GATEWAY="http://localhost:8000"

echo "========================================================================"
echo "  MiniKV v2.0 - Cluster Test Suite"
echo "========================================================================"
echo ""

# Test 1: Health Check
echo "Test 1: Cluster Health Check"
echo "----------------------------------------"
curl -s "$GATEWAY/cluster/status" | python3 -m json.tool
echo ""

# Test 2: Set Keys
echo ""
echo "Test 2: Setting Keys"
echo "----------------------------------------"
for i in {1..10}; do
    echo "Setting key$i..."
    curl -s -X POST "$GATEWAY/set/key$i" \
        -H "Content-Type: application/json" \
        -d "{\"value\": \"value$i\"}" | python3 -m json.tool
done
echo ""

# Test 3: Get Keys
echo ""
echo "Test 3: Getting Keys"
echo "----------------------------------------"
for i in {1..5}; do
    echo "Getting key$i..."
    curl -s "$GATEWAY/get/key$i" | python3 -m json.tool
done
echo ""

# Test 4: Key Distribution
echo ""
echo "Test 4: Key Distribution"
echo "----------------------------------------"
curl -s "$GATEWAY/cluster/distribution" | python3 -m json.tool
echo ""

# Test 5: Gateway Stats
echo ""
echo "Test 5: Gateway Statistics"
echo "----------------------------------------"
curl -s "$GATEWAY/stats" | python3 -m json.tool
echo ""

echo "========================================================================"
echo "  All Tests Complete!"
echo "========================================================================"

