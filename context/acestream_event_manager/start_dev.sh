#!/bin/bash

# Define log directory
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# Function to kill processes on ports
cleanup_ports() {
    echo "Cleaning up ports 3000 and 3001..."
    lsof -t -i:3000 | xargs kill -9 2>/dev/null
    lsof -t -i:3001 | xargs kill -9 2>/dev/null
}

# Cleanup function to be called on exit
cleanup() {
    echo ""
    echo "Stopping servers..."
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    # Ensure ports are clear
    cleanup_ports
    echo "Servers stopped."
    exit
}

# Trap SIGINT (Ctrl+C) and EXIT
trap cleanup SIGINT EXIT

# Initial cleanup
cleanup_ports

echo "Starting Backend..."
cd backend
npm run dev > "../$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
cd ..
echo "Backend started (PID: $BACKEND_PID). Logs: $BACKEND_LOG"

echo "Starting Frontend..."
cd frontend
npm run dev > "../$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
cd ..
echo "Frontend started (PID: $FRONTEND_PID). Logs: $FRONTEND_LOG"

echo "System is running."
echo "Press Ctrl+C to stop."
echo "Tail logs with: tail -f $LOG_DIR/*.log"

# Wait indefinitely
wait
