#!/usr/bin/env sh
set -eu

mkdir -p /app/secrets

if [ ! -f /app/secrets_config.json ]; then
  python -c 'import json; open("/app/secrets_config.json","w",encoding="utf-8").write(json.dumps({"secrets": []}, ensure_ascii=False, indent=2))'
fi

exec "$@"

