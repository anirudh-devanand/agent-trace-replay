#!/bin/sh
set -e

echo "Starting normalizer..."
exec python -m normalizer.main
