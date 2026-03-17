#!/bin/bash

# Configuration
SCRIPT_PATH="verify_loop_detection.py"
LOG_DIR="./test_results"
mkdir -p "$LOG_DIR"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}   STREAM LOOP DETECTION SCENARIO RUNNER          ${NC}"
echo -e "${BLUE}==================================================${NC}"

run_scenario() {
    local name=$1
    local mode=$2
    local loop_dur=$3
    local total_dur=$4
    local log_file="$LOG_DIR/${name}.log"

    echo -n "Running Scenario: $name ... "
    
    python3 "$SCRIPT_PATH" --mode "$mode" --loop-duration "$loop_dur" --total-duration "$total_dur" > "$log_file" 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        echo -e "  Check log: $log_file"
    fi
}

# 1. Short Loop (5s) - Detects as 10s loop (multiples of 5s)
run_scenario "short_loop_5s" "loop" 5 30

# 2. Production Threshold Loop (10s)
run_scenario "standard_loop_10s" "loop" 10 40

# 3. Long Loop (15s)
run_scenario "long_loop_15s" "loop" 15 60

# 4. Normal Stream Stability
run_scenario "normal_stream_stability" "normal" 0 60

# 5. Static Content Stability
run_scenario "static_content_stability" "static" 0 60

# 6. Marathon Test (5 minutes)
run_scenario "marathon_loop_12s" "loop" 12 300

# 7. Super Marathon (10 minutes)
run_scenario "super_marathon_loop_20s" "loop" 20 600

# 8. Hyper Marathon (20 minutes)
run_scenario "hyper_marathon_loop_30s" "loop" 30 1200

# 9. Marathon Normal (10 minutes)
run_scenario "marathon_normal_10m" "normal" 0 600

echo -e "${BLUE}==================================================${NC}"
echo -e "Tests completed. Logs available in $LOG_DIR"
