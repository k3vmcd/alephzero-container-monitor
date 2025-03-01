# Aleph Zero Container Monitor

This project provides a Dockerized Python script to monitor an Aleph Zero container and automatically restart it under specific conditions.

## Description

The script monitors an Aleph Zero container and restarts it when it falls far behind the highest known block or if it exits a major sync state and hasn't caught up yet, but isn't in the middle of (at least attempting) to produce blocks.

Specifically, it checks for the following conditions:

* **Block Lag:** If the container's synced block is more than 100 blocks behind the latest block from the Aleph Zero network, it restarts the container immediately.
* **Sync State and Block Lag:** If the container is not in a major sync state (indicated by the presence of the log message "No longer in major sync state."), the synced block is more than 20 blocks behind the latest block, and the container is not actively producing blocks in the current session, it restarts the container.
* **Block Production:** Block production is determined by the existence of log lines indicating that the container is preparing and pre-sealing blocks.
* **Session Tracking:** The script tracks the current session to ensure block production checks are relevant.
* **Latest Block Retrieval:** The script retrieves the latest block number from the Aleph Zero network using the OnFinality public RPC endpoint.

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