#!/bin/bash

# Get UID and GID from environment variables, or use defaults
UID=${MONITOR_UID:-1000}
GID=${MONITOR_GID:-1000}

# Create user and group if they don't exist
if ! getent group "$GID" > /dev/null 2>&1; then
  groupadd -g "$GID" monitorgroup
fi

if ! getent passwd "$UID" > /dev/null 2>&1; then
  useradd -u "$UID" -g "$GID" -M --no-create-home --shell /bin/false monitoruser
fi

# Change ownership of /app directory
chown -R "$UID":"$GID" /app

# Switch to the specified user and run the application
exec gosu "$UID":"$GID" python monitor.py