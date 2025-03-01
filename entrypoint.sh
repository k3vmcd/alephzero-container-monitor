#!/bin/bash

# Get UID and GID from environment variables, or use defaults
MON_UID=${MONITOR_UID:-1000}
MON_GID=${MONITOR_GID:-996}

# Create user and group if they don't exist
if ! getent group "$MON_GID" > /dev/null 2>&1; then
  groupadd -g "$MON_GID" monitorgroup
fi

if ! getent passwd "$MON_UID" > /dev/null 2>&1; then
  useradd -u "$MON_UID" -g "$MON_GID" -M --no-create-home --shell /bin/false monitoruser
fi

# Change ownership of /app directory
chown -R "$MON_UID":"$MON_GID" /app

# Switch to the specified user and run the application
exec gosu "$MON_UID":"$MON_GID" python monitor.py