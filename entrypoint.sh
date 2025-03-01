#!/bin/bash

# Get UID and GID from environment variables, or use defaults
UID=${MONITOR_UID:-1000}
GID=${MONITOR_GID:-1000}

# Create user and group if they don't exist
if ! getent group "$GID" > /dev/null 2>&1; then
  addgroup -g "$GID" monitorgroup
fi

if ! getent passwd "$UID" > /dev/null 2>&1; then
  adduser -u "$UID" -G monitorgroup -D monitoruser
fi

# Change ownership of /app directory
chown -R "$UID":"$GID" /app

# Switch to the specified user and run the application
exec su-exec "$UID":"$GID" python monitor.py