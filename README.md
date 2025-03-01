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

### Deployment

1.  **Run the Docker Container:**

    ```bash
    docker run -d \
        -e CONTAINER_NAME="your_container_name" \
        -e RPC_URL="[https://aleph-zero.api.onfinality.io/public](https://aleph-zero.api.onfinality.io/public)" \
        -e CHECK_INTERVAL=60 \
        -e BLOCK_LAG_20=20 \
        -e BLOCK_LAG_100=100 \
        --name alephzero-monitor \
        YOUR_DOCKER_HUB_USERNAME/alephzero-monitor:latest
    ```

    Replace `your_container_name` with the actual name of the Aleph Zero container you want to monitor and `YOUR_DOCKER_HUB_USERNAME` with your dockerhub username.

### Environment Variables

* `CONTAINER_NAME`: (Required) The name of the Docker container to monitor.
* `RPC_URL`: (Optional, default: `https://aleph-zero.api.onfinality.io/public`) The RPC endpoint URL for Aleph Zero.
* `CHECK_INTERVAL`: (Optional, default: `60`) The interval (in seconds) between checks.
* `BLOCK_LAG_20`: (Optional, default: `20`) The block lag threshold for restarts when not in sync.
* `BLOCK_LAG_100`: (Optional, default: `100`) The block lag threshold for immediate restarts.

### Logging

The script logs to `monitor.log` inside the Docker container. You can mount a volume to persist the logs:

```bash
docker run -d \
    -v /path/on/host/monitor.log:/app/monitor.log \
    # ... other options