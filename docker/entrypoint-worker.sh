#!/bin/sh
set -e

echo "Starting replay worker..."
exec python -m worker.main
