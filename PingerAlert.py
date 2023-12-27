import os
import time
import winsound
import multiprocessing

from enum import Enum
import pyautogui as pag
import asyncio

import constants
import ip_addresses as ips


class Status(Enum):
    DOWN = 0
    UP = 1
    UNSTABLE = 2


class ServerStatus:
    """
    Represents the status of a server.

    Attributes:
        ip (str): The IP address of the server.
        status (Status): The current status of the server.
    """

    def __init__(self, ip: str, status: Status):
        self.ip = ip
        self.status = status

    def __str__(self):
        return f"{get_name_by_ip(self.ip)} is {str(self.status.name)}!!"


def get_name_by_ip(ip: str) -> str:
    if ip not in ips.ip_addresses.keys():
        return "Unknown"
    return ips.ip_addresses[ip]


def show_alert(title, text):
    pag.alert(text=text, title=title, timeout=constants.POPUP_ALERT_TIMEOUT)


def status_alert(hostnames: list[ServerStatus]):
    """
    Prints the status for each of the given hostnames.
    Displays a popup status alert if at least one of the given hostnames is down.

    Parameters:
    - hostnames (list[ServerStatus]): A list of ServerStatus objects representing the hostnames.

    Returns:
    None
    """
    
    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)
    alert_title = "Status Alert " + current_time
    alert_text = "Alert! " + "\n"
    show_alert_ = False
    for hostname in hostnames:
        alert_text += str(hostname) + "\n"
        if hostname.status == Status.DOWN:
            show_alert_ = True
    if show_alert_: # Shows alert in a separate process
                   # to avoid blocking the main process
        process = multiprocessing.Process(target=show_alert,
                                           args=(alert_title, alert_text))
        process.start()
        winsound.PlaySound(os.path.join(constants.SOUNDS_PATH,
                                        constants.DOWN_ALERT_SOUND),
                                        winsound.SND_FILENAME)
    print("---------" + alert_title + "---------" + "\n" + alert_text)


async def async_ping(hostname):
    """
    Asynchronously pings the specified hostname once.

    Args:
        hostname (str): The hostname or IP address to ping.

    Returns:
        bool: True if the ping is successful, False otherwise.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            'ping', '-w', str(constants.PING_TIMEOUT), '-n', '1', hostname,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        output, _ = await process.communicate()
        return process.returncode == 0 and "unreachable" not in output.decode().lower()
    except:
        return False


async def host_status_check(hostname: str) -> ServerStatus:
    """
    Check the status of a host by pinging it a predefined amount of times.
    The host's status is determined by predefined percentage of successful pings.

    Args:
        hostname (str): The hostname or IP address of the host to check.

    Returns:
        ServerStatus: The status of the host.

    """
    successful_ping_counter = 0
    for _ in range(constants.MAX_PING_CHECK):
        result = await async_ping(hostname)
        if result:
            successful_ping_counter += 1

    if successful_ping_counter >= (constants.MIN_SUCCESSFUL_PERCENT * constants.MAX_PING_CHECK):
        status = Status.UP
    elif successful_ping_counter > (constants.MIN_UNSTABLE_PERCENT * constants.MAX_PING_CHECK):
        status = Status.UNSTABLE
    else:
        status = Status.DOWN
    return ServerStatus(hostname, status)


async def update_servers_status(servers_status: dict) -> dict:
    """
    Main function that performs status check for multiple hosts asynchronously.

    Args:
        servers_status (dict): A dictionary containing the current status of servers.

    Returns:
        dict: A dictionary containing the updated status of servers after the check.
    """
    
    tasks = [host_status_check(hostname) for hostname in ips.ip_addresses.keys()]
    results = await asyncio.gather(*tasks)
    changed_servers = []
    for result in results:
        if result.ip in servers_status.keys()\
                    and servers_status[result.ip] != result.status:
            changed_servers.append(result)
        servers_status[result.ip] = result.status
    if changed_servers:
        status_alert(changed_servers)
    return servers_status


async def main() -> None:
    servers_status = {}
    print(constants.APP_NAME + " has been started")
    while True:
        servers_status = await update_servers_status(servers_status)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(e)
