#! /usr/bin/env bash

/usr/bin/env bash /app/scripts/prestart.sh

exec uvicorn --host 0.0.0.0 --port 80 --reload --log-level info "main:app"