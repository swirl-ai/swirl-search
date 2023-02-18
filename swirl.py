'''
@author:     Sid Probstein
@contact:    sid@swirl.today
@version:    SWIRL 1.x
'''

import argparse
from asyncio.subprocess import STDOUT
import sys
import os
import subprocess
from subprocess import SubprocessError
import json
import time
import signal
from datetime import datetime

# import django
# from sys import path
# from os import environ
# from swirl.utils import swirl_setdir
# path.append(swirl_setdir()) # path to settings.py file
# environ.setdefault('DJANGO_SETTINGS_MODULE', 'swirl_server.settings')
# django.setup()

# from django.conf import settings

module_name = 'swirl.py'

from swirl.banner import SWIRL_BANNER, bcolors
from swirl.services import SWIRL_SERVICES, SWIRL_SERVICES_DEBUG, SWIRL_SERVICES_DICT, SWIRL_SERVICES_DEBUG_DICT, SERVICES, SERVICES_DICT

SWIRL_CORE_SERVICES = ['django', 'celery-worker']

COMMAND_LIST = [ 'help', 'start', 'debug', 'start_sleep', 'stop', 'restart', 'migrate', 'setup', 'status', 'watch', 'logs' ]

##################################################

def check_rabbit():
    proc = subprocess.run(['ps','-ef'], capture_output=True)
    result = proc.stdout.decode('UTF-8')
    list_result = []
    if '\n' in result:
        list_result = result.split('\n')
    for l in list_result:
        if 'rabbitmq' in l.lower():
            if 'grep rabbitmq' in l.lower():
                # ignore: grep rabbitmq
                pass
            else:
                return l

    return ""

def check_pid(pid):
    proc = subprocess.run(['ps','-p',str(pid)], capture_output=True)
    result = proc.stdout.decode('UTF-8')
    return str(pid) in result

def show_pids(pid_string):
    proc = subprocess.run(['ps','-p', pid_string[:-1]], capture_output=True)
    result = proc.stdout.decode('UTF-8')
    return result

##################################################

def load_swirl_file():
    if os.path.exists('.swirl'):
        try:
            swirl_file = open('./.swirl', 'r')
            dict_pid = json.load(swirl_file)
            swirl_file.close()
        except OSError as err:
            print(f"Error: {err}")
            return False
        return dict_pid
    else:
        return {}

def write_swirl_file(dict_pid):
    try:
        swirl_file = open('./.swirl', 'w')
        result = swirl_file.write(json.dumps(dict_pid))
        swirl_file.close()
    except OSError as err:
        print(f"Error: {err}")
        return False

    return True

##################################################

def launch(name, path):

    # prepare the path
    path_list = path.split()

    # create the log file
    try:
        f = open(f'./logs/{name}.log', 'wb')
    except OSError as err:
        print(f"Error: {err} creating: ./logs/{name}.log")
        return -1
    try:
        process = subprocess.Popen(path_list, stdout=f, stderr=subprocess.STDOUT)
    except Exception as err: # Broad exception okay here.
        print(f"Error: {err} creating process: {' '.join(path_list)}")
        return -1

    # do not close this file

    if process.returncode == None:
        return process.pid
    else:
        return -1

##################################################

def start(service_list):

    dict_pid = {}

    # check if .swirl exists
    dict_pid = load_swirl_file()
    if dict_pid:
        for service_name in dict_pid:
            if service_name in service_list:
                print(f"Error: {service_name} appears to be running, please check .swirl or remove it; exiting...")
                return False
        # end for
        # items in service_list are NOT in dict_pid, so continue and start them
    # end if

    if not os.path.exists('./logs'):
        print("Warning: logs directory does not exist, creating it")
        os.mkdir('./logs')

    # start service_list
    pids = ""
    flag = False
    for service_name in service_list:
        if service_name in SERVICES_DICT:
            # Fix for https://github.com/swirlai/swirl-search/issues/47
            # if service_name == 'rabbitmq':
            #     # check to see if it is running
            #     rabbit = check_rabbit()
            #     if rabbit:
            #         print(f"Warning: rabbitmq appears to be running, skipping it:\n{rabbit}")
            #         continue
            # # end if
            print(f"Start: {service_name} -> {SERVICES_DICT[service_name]} ... ", end='')
            result = launch(service_name, SERVICES_DICT[service_name])
            time.sleep(5)
            if result > 0:
                print(f'Ok, pid: {result}')
                dict_pid[service_name] = result
                pids = pids + str(result) + ','
            else:
                print(f"Error: {result}, check logs for output")
                flag = True
            # end if
        else:
            print(f"Warning: unknown service: {service_name}, ignoring")
        # end if
    # end for

    if len(dict_pid) > 0:
        # something was started, write the file
        print("Updating .swirl... ", end='')
        write_swirl_file(dict_pid)
        print("Ok")

    print()
    print(show_pids(pids))

    if flag:
        return False

    return True

##################################################

def start_sleep (service_list):

    status = start(service_list)
    return status

##################################################

def debug(service_list):
    pass

##################################################

def watch(service_list):

    while 1:
        try:
            print(datetime.now())
            print()
            x = status(service_list)
            time.sleep(60)
        except KeyboardInterrupt:
            break

    return True

##################################################

def logs(service_list):

    print("tail -f logs/*.log - hit ^C to stop:")

    try:
        p = subprocess.Popen(['tail','-f','logs/django.log','logs/celery-worker.log'], stdout=subprocess.PIPE)

        while p.poll() is None:
            l = p.stdout.readline()
            print(l.decode("utf-8").replace('\n',''))
        p.kill()
        return True

    except KeyboardInterrupt:
        p.kill()
        return True

##################################################

def status(service_list):

    # check if .swirl exists
    dict_pid = load_swirl_file()

    if not dict_pid:
        print(f"SWIRL does not appear to be running - .swirl not found")
        return True

    pid_string = ""
    for service_name in dict_pid:
        if service_name in service_list:
            pid_string = pid_string + str(dict_pid[service_name]) + ','
            print(f"Service: {service_name}...", end='')
            if check_pid(dict_pid[service_name]):
                print(f"RUNNING, pid:{dict_pid[service_name]}")
            else:
                print(f"UNKNOWN, pid:{dict_pid[service_name]} not found")
            # end if
        # end if
    # end for

    print()
    print(show_pids(pid_string))

    return True

##################################################

def migrate(service_list):

    print("Checking Migrations:")

    any_change = False

    proc = subprocess.run(['python','manage.py','makemigrations'], capture_output=True)
    if proc.returncode != 0:
        print(f"Error: {proc.stderr.decode('UTF-8')}")
        return False
    result = proc.stdout.decode('UTF-8')
    if not 'No changes detected' in result:
        any_change = True
    else:
        print(result)

    proc = subprocess.run(['python','manage.py','makemigrations','swirl'], capture_output=True)
    if proc.returncode != 0:
        print(f"Error: {proc.stderr.decode('UTF-8')}")
        return False
    result = proc.stdout.decode('UTF-8')
    if not 'No changes detected' in result:
        any_change = True
    else:
        print(result)

    print()
    print("Migrating:")
    print()

    proc = subprocess.run(['python','manage.py','migrate'], capture_output=True)
    if proc.returncode != 0:
        print(f"Error: {proc.stderr.decode('UTF-8')}")
        return False
    result = proc.stdout.decode('UTF-8')
    print(result)
    return True

##################################################

def stop(service_list):

    dict_pid = {}

    # check if .swirl exists
    dict_pid = load_swirl_file()

    if not dict_pid:
        print(f"Error: .swirl not found, exiting")
        return False

    # stop service_list
    pids = ""
    stopped_names = []
    flag = False
    for service_name in dict_pid:
        # if in .swirl
        if service_name in service_list:
            # if specified as argument to command
            if service_name == SERVICES[0]['name']:
                # except for the first listed service
                continue
            print(f"Stop: {service_name}, pid: {dict_pid[service_name]}... ", end='')
            pid = int(dict_pid[service_name])
            try:
                os.kill(pid, 0)  # if the pid doesn't exist, this will throw an exception
                os.kill(pid, signal.SIGTERM)
            except OSError as err:
                print(f"Error: {err}")
                flag = True
            time.sleep(10)
            # confirm
            if check_pid(pid):
                print(f"Error: still running!")
                flag = True
            else:
                print(f"Ok")
                stopped_names.append(service_name)
            pids = pids + str(pid) + ','
            # end if
        # end if
    # end for

    # shut down the first service, last - IF specified
    if SERVICES[0]['name'] in dict_pid:
        if SERVICES[0]['name'] in service_list:
            print(f"Stop: {SERVICES[0]['name']}, pid_group: {dict_pid[SERVICES[0]['name']]}... ", end='')
            pid = int(dict_pid[SERVICES[0]['name']])
            try:
                pgrp = os.getpgid(pid)
                os.killpg(pgrp, signal.SIGTERM)
                # os.kill(pid, 0)  # if the pid doesn't exist, this will throw an exception
                # os.kill(pid, signal.SIGTERM)
            except OSError as err:
                print(f"Error: {err}")
                flag = True
            time.sleep(10)
            # confirm
            if check_pid(pid):
                print(f"Error: still running!")
                flag = True
            else:
                print(f"Ok")
                stopped_names.append(SERVICES[0]['name'])
            pids = pids + str(pid) + ','
            # end if
    # end if

    print()
    print(show_pids(pids))

    for service_name in stopped_names:
        del dict_pid[service_name]

    if dict_pid:
        # print("Removing stopped services from .swirl... ", end='')
        write_swirl_file(dict_pid)
        # print("Ok")

    if flag:
        print("Warning: at least one error occured, check .swirl for remaining pids")
        return False

    if not dict_pid:
        # print("All services stopped, removing .swirl... ", end='')
        try:
            os.remove('.swirl')
        except OSError as err:
            print(f"Error: {err}")
            return False
        # print("Ok")
    # end if

    return True

##################################################

def restart(service_list):

    print(f"Restart: {', '.join(service_list)}")

    result = stop(service_list)
    if result:
        time.sleep(5)
        result = start(service_list)
    else:
        print(f"Error stopping: {' '.join(service_list)}")
        return result
    # end if

    if not result:
        print(f"Error starting: {' '.join(service_list)}")

    return result

##################################################

def help(service_list):
    print("Usage: python swirl.py <command> [<service-list>]\n")
    print(f"Available commands: {', '.join(COMMAND_LIST)}")
    print(f"Available services: {', '.join(SERVICES_DICT.keys())}, core ({', '.join(SWIRL_CORE_SERVICES)})\n")
    print("The start, status, stop and restart commands default to all SWIRL services.")
    print("Most optionally accept one or more SWIRL service names, separated by spaces.")
    print()
    result = True

##################################################

def setup(service_list):

    print("Setting Up SWIRL:")

    result = migrate(service_list)
    if not result:
        print(f"Error: error during migration, check console output")
        return False

    if not os.path.exists(os.getcwd() + '/static'):
        # collect statics
        print()
        print(f"Collecting Statics:")
        print()
        proc = subprocess.run(['python','manage.py','collectstatic'], capture_output=True)
        if proc.returncode != 0:
            print(f"Error: {proc.stderr.decode('UTF-8')}")
            return False
        result = proc.stdout.decode('UTF-8')
        print(result)
        if 'static files copied' in result:
            print("Ok")
            return True
        else:
            return False
    else:
        return True

##################################################
##################################################

COMMAND_DIR = {}
for command in COMMAND_LIST:
    COMMAND_DIR[command] = eval(command)

def main(argv):
    global SERVICES
    global SERVICES_DICT

    print(f"{SWIRL_BANNER}")
    print()

    parser = argparse.ArgumentParser(description="Manage the SWIRL server")
    parser.add_argument('command', nargs='+', help="Specify 'help' to get a list of available commands")
    parser.add_argument('-d', '--debug', action="store_true", help="start SWIRL in debug mode")
    args = parser.parse_args()

    if args.debug:
        SERVICES = SWIRL_SERVICES_DEBUG
        SERVICES_DICT = SWIRL_SERVICES_DEBUG_DICT

    # check to see that we are in a directory with swirl under it, and manage.py in it
    dir = os.getcwd()
    if not os.path.exists(dir + '/swirl'):
        print(f"{bcolors.FAIL}Error: swirl subdirectory is missing, are you sure '{dir}' is the right directory?{bcolors.ENDC}")
    if not os.path.exists(dir + '/manage.py'):
        print(f"{bcolors.FAIL}Error: manage.py is missing, are you sure '{dir}' is the right directory?{bcolors.ENDC}")

    if not args.command[0] in COMMAND_LIST:
        print(f"Unknown command: '{args.command[0]}'")
        return 0
    else:
        service_list = args.command[1:]
        if service_list == [] or service_list[0].lower() == 'all':
            service_list = []
            for service in SERVICES:
                service_list.append(service['name'])
        elif service_list[0].lower() == 'core':
            service_list = SWIRL_CORE_SERVICES
        else:
            for service in service_list:
                if not service in SERVICES_DICT:
                    print(f"{bcolors.WARNING}Unknown service: {service}{bcolors.ENDC}")
                    print(f"Available services: ", end='')
                    for swirl_service in SERVICES_DICT:
                        print(f"{swirl_service} ", end='')
                    print()
                    return False
                # end if
            # end for
        # run the command
        command = args.command[0]
        # limit eval for security purposes
        result = eval(command + '(service_list)', {"command": command, "service_list": service_list, "__builtins__": None}, COMMAND_DIR)
    # end if

    if result == False:
        print(f"{bcolors.FAIL}Command {args.command[0]} reported an error{bcolors.ENDC}")
        return 1
    else:
        print(f"{bcolors.OKGREEN}Command successful!{bcolors.ENDC}")
        if args.command[0] == 'start_sleep':
            while 1:
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    return 0
        else:
            return 0
    # end if

#############################################

if __name__ == "__main__":
    main(sys.argv)

# end
