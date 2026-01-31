#!/usr/bin/env sh
set -eu

mkdir -p /app/secrets

SECRETS_CONFIG_PATH="${SECRETS_CONFIG_PATH:-/app/secrets/secrets_config.json}"
SECRETS_CONFIG_DIR="$(dirname "$SECRETS_CONFIG_PATH")"
mkdir -p "$SECRETS_CONFIG_DIR"

if [ ! -f "$SECRETS_CONFIG_PATH" ]; then
  python -c 'import json, os; p=os.environ.get("SECRETS_CONFIG_PATH","/app/secrets/secrets_config.json"); open(p,"w",encoding="utf-8").write(json.dumps({"secrets": []}, ensure_ascii=False, indent=2))'
fi

exec "$@"

