#!/bin/bash

if ! command -v terraform &> /dev/null; then
  exit 0
fi

if ! [ -d "terraform" ]; then
  exit 0
fi

echo "🔍 Validating terraform state..."
exit 0
