#!/bin/bash

# Deploy script for Linux server
# This script helps deploy the Next.js app correctly to avoid cross-platform issues

echo "🚀 Deploying Next.js app to Linux server..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "This script should be run on the Linux server"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    print_error "npm is not installed. Please install npm first."
    exit 1
fi

print_status "Node.js version: $(node --version)"
print_status "npm version: $(npm --version)"

# Check if package.json exists
if [ ! -f "package.json" ]; then
    print_error "package.json not found. Make sure you're in the correct directory."
    exit 1
fi

# Clean previous build
print_status "Cleaning previous build..."
rm -rf .next
rm -rf node_modules/.cache

# Install dependencies
print_status "Installing dependencies..."
if npm ci; then
    print_status "Dependencies installed successfully"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Build the application
print_status "Building the application for Linux..."
if npm run build; then
    print_status "Build completed successfully"
else
    print_error "Build failed"
    exit 1
fi

# Check if .next directory was created
if [ ! -d ".next" ]; then
    print_error ".next directory not found after build"
    exit 1
fi

print_status "Build artifacts created:"
ls -la .next/

# Test the build
print_status "Testing the build..."
timeout 10s npm start &
START_PID=$!
sleep 5

# Check if the process is still running
if kill -0 $START_PID 2>/dev/null; then
    print_status "Application started successfully"
    kill $START_PID
else
    print_error "Application failed to start"
    exit 1
fi

print_status "✅ Deployment completed successfully!"
print_status "You can now run 'npm start' to start the application"

# Optional: Start the application
read -p "Do you want to start the application now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Starting the application..."
    npm start
fi
