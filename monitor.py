import subprocess
import re
import time
import os
import logging
import signal
import sys
import requests
import json
from collections import deque

# Configuration via environment variables
CONTAINER_NAME = os.environ.get("CONTAINER_NAME")
RPC_URL = os.environ.get("RPC_URL", "https://aleph-zero.api.onfinality.io/public")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 60))
BLOCK_LAG_20 = int(os.environ.get("BLOCK_LAG_20", 20))
BLOCK_LAG_100 = int(os.environ.get("BLOCK_LAG_100", 100))
COOLDOWN_PERIOD = 300  # 5 minutes in seconds
TREND_WINDOW = 300  # 5 minutes for trend analysis
STALL_DURATION = 180  # 3 minutes for stall detection

# Logging setup - Output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

# Global variables
last_restart_time = 0
last_synced_block = None
last_check_time = None
lag_history = deque(maxlen=int(TREND_WINDOW / CHECK_INTERVAL) + 1)  # ~5 checks
stall_start_time = None

# Signal handling
def signal_handler(sig, frame):
    logging.info("Graceful shutdown initiated.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_latest_block_from_rpc(rpc_url):
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
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--tail", "5000", container_name],
            text=True,
            stderr=subprocess.STDOUT
        )
        logging.info(f"Fetched {len(logs.splitlines())} lines from docker logs")
        synced_blocks = re.findall(r"Imported #(\d+) \(0x", logs)
        if synced_blocks:
            latest_synced_block = int(synced_blocks[-1])
            logging.info(f"Latest synced block retrieved: {latest_synced_block}")
            return latest_synced_block
        else:
            logging.error(f"Could not retrieve latest synced block. Log sample: {logs[-500:]}")
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting Docker logs: {e}")
        return None

def check_major_sync_state(container_name):
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--tail", "5000", container_name],
            text=True,
            stderr=subprocess.STDOUT
        )
        sync_starts = [line for line in logs.splitlines() if "Switched to major sync state." in line]
        sync_ends = [line for line in logs.splitlines() if "No longer in major sync state." in line]
        if sync_starts and (not sync_ends or sync_starts[-1] > sync_ends[-1]):
            logging.info("Container is in a major sync state.")
            return True
        else:
            logging.info("Container is not in a major sync state.")
            return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting Docker logs: {e}")
        return False

def was_recently_restarted(container_name):
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--since", "5m", container_name],
            text=True,
            stderr=subprocess.STDOUT
        )
        if "Aleph Node" in logs:
            logging.info("Container was recently restarted within 5 minutes.")
            return True
        return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Error checking restart status: {e}")
        return False

def check_block_production(container_name, current_session):
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--since", f"{current_session}", container_name],
            text=True,
            stderr=subprocess.STDOUT
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
    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--tail", "1000", container_name],
            text=True,
            stderr=subprocess.STDOUT
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

def calculate_sync_metrics(current_time, latest_rpc_block, latest_synced_block):
    global last_synced_block, last_check_time
    lag = latest_rpc_block - latest_synced_block
    caught_up = 0
    sync_rate = 0.0
    time_to_catch_up = float('inf')

    if last_synced_block is not None and last_check_time is not None:
        caught_up = latest_synced_block - last_synced_block
        time_elapsed = current_time - last_check_time
        sync_rate = caught_up / time_elapsed if time_elapsed > 0 else 0.0
        time_to_catch_up = lag / sync_rate if sync_rate > 0 else float('inf')

    last_synced_block = latest_synced_block
    last_check_time = current_time
    return lag, caught_up, sync_rate, time_to_catch_up

def is_falling_behind():
    if len(lag_history) < 2:
        return False
    avg_lag_increase = sum(b - a for a, b in zip(lag_history, list(lag_history)[1:])) / (len(lag_history) - 1)
    return avg_lag_increase > 0 and len(lag_history) >= int(TREND_WINDOW / CHECK_INTERVAL)

def check_stall(current_time, caught_up):
    global stall_start_time
    if caught_up == 0 and last_synced_block is not None:
        if stall_start_time is None:
            stall_start_time = current_time
        elif current_time - stall_start_time >= STALL_DURATION:
            return True
    else:
        stall_start_time = None
    return False

def monitor_container(container_name, rpc_url):
    global last_restart_time, lag_history, stall_start_time

    current_time = time.time()
    time_since_last_restart = current_time - last_restart_time

    if time_since_last_restart < COOLDOWN_PERIOD:
        logging.info(f"Container {container_name} was restarted {time_since_last_restart:.0f}s ago. Waiting for {COOLDOWN_PERIOD}s cooldown.")
        return

    latest_rpc_block = get_latest_block_from_rpc(rpc_url)
    if latest_rpc_block is None:
        return

    latest_synced_block = get_latest_synced_block(container_name)
    if latest_synced_block is None:
        return

    lag, caught_up, sync_rate, time_to_catch_up = calculate_sync_metrics(current_time, latest_rpc_block, latest_synced_block)
    lag_history.append(lag)

    if lag == 0:
        logging.info(f"Container {container_name} is fully caught up at block #{latest_synced_block}.")
    else:
        logging.info(f"Container {container_name} - Lag: {lag} blocks, Caught up: {caught_up} blocks, Sync rate: {sync_rate:.2f} blocks/s, ETA to catch up: {time_to_catch_up:.0f}s")

    is_in_major_sync = check_major_sync_state(container_name)
    recently_restarted = was_recently_restarted(container_name)
    if recently_restarted:
        logging.info(f"Container {container_name} was recently restarted (post-cooldown check).")

    current_session = get_current_session(container_name)
    if current_session is None:
        return

    is_producing_blocks = check_block_production(container_name, current_session)

    # Stall detection: no progress for 3 minutes
    stalled = check_stall(current_time, caught_up) if not is_producing_blocks else False
    falling_behind = is_falling_behind() if not is_producing_blocks else False

    # Restart for severe lag, or stall/falling behind if not producing blocks
    if lag > BLOCK_LAG_100 or (not is_producing_blocks and (stalled or falling_behind)):
        if stalled:
            logging.info(f"Container {container_name} sync stalled for {STALL_DURATION}s (no progress).")
        if falling_behind:
            logging.info(f"Container {container_name} falling behind (avg lag increase over {TREND_WINDOW}s).")
        if lag > BLOCK_LAG_100:
            logging.info(f"Container {container_name} is behind by {lag} blocks (>100). Restarting...")
        else:
            logging.info(f"Restarting container {container_name}...")
        try:
            subprocess.run(["docker", "restart", container_name], check=True)
            last_restart_time = current_time
            lag_history.clear()
            stall_start_time = None
            return
        except subprocess.CalledProcessError as e:
            logging.error(f"Error restarting container: {e}")
            return

    # Normal checks only if not stalled or falling behind
    if is_in_major_sync:
        logging.info(f"Container {container_name} is in major sync state. Skipping restart.")
        return

    if is_producing_blocks:
        return  # No further checks if producing blocks

    if lag > BLOCK_LAG_20:
        logging.info(f"Container {container_name} is behind by {lag} blocks (>20) and not syncing/producing. Restarting...")
        try:
            subprocess.run(["docker", "restart", container_name], check=True)
            last_restart_time = current_time
            lag_history.clear()
            stall_start_time = None
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