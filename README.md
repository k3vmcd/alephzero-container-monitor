# Aleph Zero Container Monitor

This project provides a Dockerized Python script to monitor an Aleph Zero container and automatically restart it under specific conditions.

⚠️ **DIRE WARNING: USE AT YOUR OWN RISK** ⚠️  
This script interacts with your Docker daemon via the Docker socket, granting it significant control over your system. It can restart containers, potentially disrupt operations, and, if misconfigured, cause data loss, downtime, or security vulnerabilities. There are no guarantees of stability, safety, or correctness. Proceed with extreme caution, thoroughly test in a non-production environment, and understand the risks before deploying. The authors are not liable for any damage or issues arising from its use.


## Description

This project provides a Dockerized Python script to monitor an Aleph Zero container and automatically restart it under specific conditions to maintain synchronization with the Aleph Zero network.

The script monitors an Aleph Zero container and restarts it based on block lag, sync state, block production status, and sync progress trends, with the following logic:

*   **Cooldown Period**: After a restart, the script enforces a 5-minute (300-second) cooldown period before considering another restart. This prevents rapid restart loops and gives the container time to stabilize and begin syncing. If the time since the last restart is less than 300 seconds, it logs "Container {container\_name} was restarted {time\_since\_last\_restart}s ago. Waiting for 300s cooldown" and skips all further checks until the cooldown expires.
    

*   **Block Lag Checks**:
    
    *   **Severe Lag (>100 Blocks)**: If the container’s latest synced block is more than 100 blocks behind the latest block from the Aleph Zero network (retrieved via RPC), it logs "Container {container\_name} is behind by {lag} blocks (>100). Restarting..." and restarts the container immediately after the cooldown period, regardless of sync state or block production. This threshold is configurable via the BLOCK\_LAG\_100 environment variable (default: 100).
        
    
    *   **Moderate Lag (>20 Blocks)**: If the lag exceeds 20 blocks, the container is not in a major sync state, and it’s not producing blocks in the current session, it logs "Container {container\_name} is behind by {lag} blocks (>20) and not syncing/producing. Restarting..." and restarts after the cooldown period. This threshold is configurable via the BLOCK\_LAG\_20 environment variable (default: 20).
        
    

*   **Sync Stall Detection**: If the container makes no progress (no blocks synced since the last check) for at least 3 minutes (180 seconds), it logs "Container {container\_name} sync stalled for 180s (no progress)". However, a restart only occurs if the lag exceeds 100 blocks (BLOCK\_LAG\_100) and the container is not producing blocks, ensuring that a stall alone doesn’t trigger a restart when the container is caught up or within acceptable ranges.
    

*   **Falling Behind Detection**: The script tracks lag over a 5-minute window (300 seconds, approximately 5 checks at 60-second intervals). If the average lag increases consistently over this period, it logs "Container {container\_name} falling behind (avg lag increase over 300s)". A restart is triggered only if the lag exceeds 100 blocks (BLOCK\_LAG\_100) and the container is not producing blocks, preventing restarts when the lag is minor or managed.
    

*   **Major Sync State**: The script checks the container’s logs for "Switched to major sync state." and "No longer in major sync state." messages. It considers the container to be in a major sync state if there’s a "Switched" message without a subsequent "No longer" message (or if the last "Switched" is more recent). It logs "Container is in a major sync state." or "Container is not in a major sync state." accordingly. Normally, being in a major sync state skips restarts unless the lag exceeds 100 blocks, in which case it proceeds regardless of sync state.
    

*   **Block Production**: For moderate lag (>20 blocks), stall (3 minutes), or falling behind (5 minutes) scenarios, the script checks if the container is producing blocks by looking for "Prepared block for proposing" and "Pre-sealed block for proposal" messages in the logs since the current session began. It logs "Container is producing blocks." or "Container is not producing blocks." If producing blocks, no restart occurs for these conditions (except severe lag >100 blocks), assuming it’s functioning correctly despite lag or lack of sync progress.
    

*   **Session Tracking**: The script retrieves the current session number from logs (via "Running session ") and logs "Current session retrieved: {current\_session}" to ensure block production checks are relevant to the latest operational context.
    

*   **Sync Metrics Logging**: Each check logs:
    
    *   Current lag (difference between network best block and synced block): "Container {container\_name} - Lag: {lag} blocks".
        
    
    *   Blocks caught up since the last check: "Caught up: {caught\_up} blocks".
        
    
    *   Estimated sync rate: "Sync rate: {sync\_rate:.2f} blocks/s".
        
    
    *   Estimated time to catch up: "ETA to catch up: {time\_to\_catch\_up:.0f}s".
        
    
    *   If fully synced (lag = 0), it logs "Container {container\_name} is fully caught up at block #{latest\_synced\_block}".
        
    

*   **Latest Block Retrieval**: The latest network block number is fetched from the Aleph Zero network using the OnFinality public RPC endpoint (chain\_getHeader method), configurable via the RPC\_URL environment variable. It logs "Latest RPC block retrieved: {block\_number}".
    

The script runs continuously, checking conditions every 60 seconds (configurable via CHECK\_INTERVAL), and uses the last 5000 log lines for most checks to balance performance and accuracy. Detailed logs include fetch counts ("Fetched {lines} lines from docker logs") and session retrievals for transparency.


## Usage

### Prerequisites

* Docker installed
* Verify your Docker group GID on the host and set MONITOR_GID:
  ```bash
  ls -ln /var/run/docker.sock
  ```
  - This shows the ownership of the Docker socket (e.g., srw-rw---- 1 0 996 ...). The second number (e.g., 996) is the GID of the docker group. Adjust MONITOR_GID if it differs from the default (996).

### Deployment

1.  **Run the Docker Container:**

    ```bash
    docker run -d \
        -e CONTAINER_NAME="your_container_name" \
        -e RPC_URL="https://aleph-zero.api.onfinality.io/public" \
        -e CHECK_INTERVAL=60 \
        -e BLOCK_LAG_20=20 \
        -e BLOCK_LAG_100=100 \
        -e MONITOR_UID=1000 \
        -e MONITOR_GID=996 \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --name alephzero-monitor \
        k3vmcd/alephzero-container-monitor:latest
    ```

    Replace `your_container_name` with the actual name of the Aleph Zero container you want to monitor. Adjust MONITOR_GID if your host’s docker GID differs from the default (996).

    **Minimal Version Using Defaults**
    ```bash
    docker run -d \
        -e CONTAINER_NAME="your_container_name" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        --name alephzero-monitor \
        k3vmcd/alephzero-container-monitor:latest
    ```

### Environment Variables

* `CONTAINER_NAME`: (Required) The name of the Docker container to monitor.
* `RPC_URL`: (Optional, default: `https://aleph-zero.api.onfinality.io/public`) The RPC endpoint URL for Aleph Zero.
* `CHECK_INTERVAL`: (Optional, default: `60`) The interval (in seconds) between checks.
* `BLOCK_LAG_20`: (Optional, default: `20`) The block lag threshold for restarts when not in sync.
* `BLOCK_LAG_100`: (Optional, default: `100`) The block lag threshold for immediate restarts.
* `MONITOR_UID`: (Optional, default: `1000`) The User ID that the container will run as.
* `MONITOR_GID`: (Optional, default: `996`) The Group ID that the container will run as.

### Security Considerations

* **Docker Socket Mount:** The `-v /var/run/docker.sock:/var/run/docker.sock` option mounts the Docker socket into the container. This grants the container significant privileges, allowing it to control the Docker daemon.
* **Security Risks:** Be aware that this approach introduces security risks. Any process running inside the `alephzero-monitor` container can potentially control the host system.
* **Production Environments:** Exercise caution when using this approach in production environments. Consider alternative solutions if security is a primary concern.
* **Restricted Access:** If possible, limit the privileges of the user running inside the container.
* **User Configuration:** The container runs as a non-root user for improved security. The `MONITOR_UID` and `MONITOR_GID` environment variables can be used to configure the User ID and Group ID that the container will use.
* **Docker Socket Permissions:** The user running the container (specified by `MONITOR_UID` and `MONITOR_GID`) must have read and write permissions to the Docker socket (`/var/run/docker.sock`). In most cases, this means the user needs to be a member of the `docker` group on the host system (default GID: 996 in this image).

### Logging

The script logs to stdout, which can be viewed using:

```bash
    docker logs alephzero-monitor
```