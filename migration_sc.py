import os
import subprocess
import json
from getpass import getpass, getuser
import logging
import sys
from datetime import datetime

# Set the logging level to DEBUG to get all output
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Custom exception for command execution failure
class CommandExecutionFailed(Exception):
    pass

def run_command(command):
    log_dir = "/opt/script_migration_sc/"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "migration_sc_logfile.log")
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, encoding='utf-8')
        with open(log_file_path, "a") as logfile:
            print(result.stdout, file=logfile)
            return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution failed: {command}")
        logger.error(f"Error: {e.stderr.strip()}")
        raise CommandExecutionFailed(f"Failed to execute command: {command}")

def save_progress(step):
    progress = {'current_step': step}
    with open('migration_save_progress', 'w') as file:
        json.dump(progress, file)

def load_progress():
    try:
        with open('migration_save_progress', 'r') as file:
            progress = json.load(file)
            return progress['current_step']
    except FileNotFoundError:
        return None

def ask_user(question):
    response = input(question).lower()
    if response == 'c':
        logger.info("Process cancelled by user.")
        raise SystemExit("User cancelled the process")
    elif response == 'n':
        return False
    elif response == 'y' or response == '':
        return True
    else:
        logger.warning("Invalid response. Please enter 'Y' or press 'Enter' to continue, 'N' to cancel.")
        return ask_user(question)

def manage_services(services, operation):
    for service in services:
        if operation == "start":
            command = ["service", service, "start"]
        elif operation == "stop":
            command = ["service", service, "stop"]
        run_command(command)

def rsync_transfer(source, destination, password):
    run_command(["rsync", "-avzhe", "--progress", f"sshpass -p '{password}'", "ssh", "-o", "StrictHostKeyChecking=no", source, destination, "--rsync-path=sudo rsync"])

def main():
    current_step = load_progress()
    if current_step is not None:
        logger.info(f"Resuming from step {current_step + 1}")
    else:
        logger.info("Starting from the beginning")
        
    # Step 11: Create Pg_Dump
    if current_step is None or current_step < 11:
        try:
            run_command(["mkdir", "-p", "/opt/Backups/"])
            run_command(["pg_dump", "-Upostgres", "-Fc", "securechangeworkflow", "-f", "/opt/Backups/sc_pg.tar"])
            save_progress(11)
        except CommandExecutionFailed:
            logger.error("Failed to create Pg_Dump.")
            raise
        
    # Step 12: Transfer Pg_Dump
    if current_step is None or current_step < 12:
        if not ask_user("Would you like to transfer the file? (yes/no)"):
            logger.info("Process cancelled by user.")
            raise SystemExit("User cancelled the process")
        try:
            username = getuser()
            ip = input("Please enter your IP address: ")
            password = getpass("Please enter your SSH password: ")
            rsync_transfer("/opt/Backups/sc_pg.tar", f"{username}@{password}:/opt/tufin/migration_sc/sc_pg.tar")
            save_progress(12)
        except CommandExecutionFailed:
            logger.error("Failed to transfer Pg_Dump.")
            raise
        
    # Step 13: Stop services
    if current_step is None or current_step < 14:
        try:
            services = ["tomcat", "mongod", "postgresql-11"]
            manage_services(services, "stop")
        except CommandExecutionFailed:
            logger.error("Failed to stop services.")
            raise
        save_progress(14)
        
    # Step 14: Transfer Catalina and Mongo files
    if current_step is None or current_step < 15:
        try:
            username = getuser()
            ip = input("Please enter your IP address: ")
            password = getpass("Please enter your SSH password: ")
            rsync_transfer("/var/lib/mongo/", f"{username}@{ip}:/opt/tufin/data/volumes/mongo-sc-rs/")
            rsync_transfer("/usr/tomcat-8.5.61/conf/catalina.conf", f"{username}@{ip}:/opt/tufin/data/volumes/migration-pv/sc/conf/catalina.conf")
        except CommandExecutionFailed:
            logger.error("Failed to transfer Catalina and Mongo files.")
            raise
        save_progress(15)
        
    # Step 15: Start Services
    if current_step is None or current_step < 16:
        try:
            services = ["tomcat", "mongod", "postgresql-11"]
            manage_services(services, "start")
        except CommandExecutionFailed:
            logger.error("Failed to start services.")
            raise
        save_progress(16)
        
    # Final
    logger.info("Migration process completed successfully.")

if __name__ == "__main__":
    main()
