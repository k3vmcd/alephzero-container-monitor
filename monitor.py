import subprocess
import re
import time
import os
import logging
import signal
import sys
import requests
import json

# Configuration via environment variables
CONTAINER_NAME = os.environ.get("CONTAINER_NAME")
RPC_URL = os.environ.get("RPC_URL", "https://aleph-zero.api.onfinality.io/public")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 60))
BLOCK_LAG_20 = int(os.environ.get("BLOCK_LAG_20", 20))
BLOCK_LAG_100 = int(os.environ.get("BLOCK_LAG_100", 100))

# Logging setup
logging.basicConfig(filename="monitor.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Signal handling
def signal_handler(sig, frame):
    logging.info("Graceful shutdown initiated.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_latest_block_from_rpc(rpc_url):
    """Fetches the latest block number using chain_getHeader."""
    try:
        payload = {"id": 1, "jsonrpc": "2.0", "method": "chain_getHeader"}
        headers = {'Content-Type': 'application/json'}
        response = requests.post(rpc_url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json().get('result')
        if result and 'number' in result:
            block_number = int(result['number'], 16)
            logging.info(f"Latest RPC block retrieved: {block_number}")
            return block_number
        else:
            logging.error("Could not retrieve block number from RPC response.")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching latest block from RPC: {e}")
        return None
    except (KeyError, ValueError, AttributeError) as e:
        logging.error(f"Error parsing RPC response: {e}")
        return None

def get_latest_synced_block(container_name):
    """Extracts the latest synced block number from Docker logs."""
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--tail", "5000", container_name], text=True
        )
        synced_blocks = re.findall(r"Imported #(\d+) \(0x", logs)
        if synced_blocks:
            latest_synced_block = int(synced_blocks[-1])
            logging.info(f"Latest synced block retrieved: {latest_synced_block}")
            return latest_synced_block
        else:
            logging.error("Could not retrieve latest synced block from Docker logs.")
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting Docker logs: {e}")
        return None
    except ValueError:
        return None

def check_major_sync_state(container_name):
    """Checks if the container is in a major sync state."""
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--tail", "5000", container_name], text=True
        )
        if "No longer in major sync state." in logs:
            logging.info("Container is not in a major sync state.")
            return True
        else:
            logging.info("Container is in a major sync state.")
            return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting Docker logs: {e}")
        return False

def check_block_production(container_name, current_session):
    """Checks if the container is producing blocks during the current session."""
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--since", f"{current_session}", container_name], text=True
        )
        if "Prepared block for proposing" in logs and "Pre-sealed block for proposal" in logs:
            logging.info("Container is producing blocks.")
            return True
        else:
            logging.info("Container is not producing blocks.")
            return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting Docker logs: {e}")
        return False

def get_current_session(container_name):
    """Gets the current session from the docker logs."""
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--tail", "1000", container_name], text=True
        )
        sessions = re.findall(r"Running session (\d+)", logs)
        if sessions:
            current_session = sessions[-1]
            logging.info(f"Current session retrieved: {current_session}")
            return current_session
        else:
            logging.error("Could not retrieve current session from Docker logs.")
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting Docker logs: {e}")
        return None

def monitor_container(container_name, rpc_url):
    """Monitors the container and restarts it if necessary."""
    latest_rpc_block = get_latest_block_from_rpc(rpc_url)
    if latest_rpc_block is None:
        logging.error("Latest RPC block not retrieved.")
        return

    latest_synced_block = get_latest_synced_block(container_name)
    if latest_synced_block is None:
        logging.error("Latest synced block not retrieved.")
        return

    block_lag = latest_rpc_block - latest_synced_block

    if block_lag > BLOCK_LAG_100:
        logging.info(f"Container {container_name} is behind by more than 100 blocks. Restarting...")
        try:
            subprocess.run(["docker", "restart", container_name], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error restarting container: {e}")
        return

    is_not_syncing = check_major_sync_state(container_name)
    if is_not_syncing is False:
        logging.info("Container is still in major sync state.")
        return

    current_session = get_current_session(container_name)
    if current_session is None:
        logging.error("Could not retrieve current session.")
        return

    is_producing_blocks = check_block_production(container_name, current_session)
    if is_producing_blocks is True:
        logging.info("Container is producing blocks.")
        return
    else:
        logging.info("Container is not producing blocks.")

    if block_lag > BLOCK_LAG_20:
        logging.info(f"Container {container_name} is behind by more than 20 blocks and not syncing. Restarting...")
        try:
            subprocess.run(["docker", "restart", container_name], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error restarting container: {e}")

if __name__ == "__main__":
    logging.info("Starting container monitor.")
    while True:
        if not CONTAINER_NAME:
            logging.error("CONTAINER_NAME environment variable is not set. Exiting.")
            sys.exit(1)
        monitor_container(CONTAINER_NAME, RPC_URL)
        time.sleep(CHECK_INTERVAL)
    logging.info("Stopping container monitor.")