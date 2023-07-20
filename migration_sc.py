import os
import subprocess
import json
from getpass import getpass, getuser
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        sys.exit(1)

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
        sys.exit(0)
    elif response == 'n':
        return False
    elif response == 'y' or response == '':
        return True
    else:
        logger.warning("Invalid response. Please enter 'Y' or press 'Enter' to continue, 'N' to cancel.")
        return ask_user(question)

def manage_services(commands):
    for command in commands:
        run_command(command.split())

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
        except subprocess.CalledProcessError:
            logger.error("Failed to create Pg_Dump.")
            sys.exit(1)
    
    # Step 12: Transfer Pg_Dump
    if current_step is None or current_step < 12:
        if not ask_user("Would you like to transfer the file? (yes/no)"):
            logger.info("Process cancelled by user.")
            sys.exit(0)
        try:
            run_command(["rsync", "-avzhe", "--progress", f"sshpass -p '{password}'", "ssh", "-o", "StrictHostKeyChecking=no",
            "/opt/Backups/sc_pg.tar", f"{username}@{password}:/opt/tufin/migration_sc/sc_pg.tar", "--rsync-path=sudo rsync"])
            save_progress(12)
        except subprocess.CalledProcessError:
            logger.error("Failed to transfer Pg_Dump.")
            sys.exit(1)
    
    # Step 13: Stop services
    if current_step is None or current_step < 14:
        try:
            commands = [
                "service tomcat stop"
                "service mongod stop"
                "service postgresql-11 stop"
            ]
            manage_services(commands)
        except subprocess.CalledProcessError:
            logger.error("Failed to stop services.")
            sys.exit(1)
        save_progress(14)
    
    # Step 14: Transfer Catalina and Mongo files
    if current_step is None or current_step < 15:
        try:
            username = getuser()
            ip = input("Please enter your IP address: ")
            password = getpass("Please enter your SSH password: ")
            run_command(["rsync", "-avzhe", "--progress", f"sshpass -p '{password}'", "ssh", "-o", "StrictHostKeyChecking=no",
                "/var/lib/mongo/", f"{username}@{ip}:/opt/tufin/data/volumes/mongo-sc-rs/", "--rsync-path=sudo rsync"])
            run_command(["rsync", "-avzhe", "--progress", f"sshpass -p '{password}'", "ssh", "-o", "StrictHostKeyChecking=no",
                "/usr/tomcat-8.5.61/conf/catalina.conf", f"{username}@{ip}:/opt/tufin/data/volumes/migration-pv/sc/conf/catalina.conf", "--rsync-path=sudo rsync"])
        except subprocess.CalledProcessError:
            logger.error("Failed to transfer Catalina and Mongo files.")
            sys.exit(1)
        save_progress(15)
    
    # Step 15: Start Services
    if current_step is None or current_step < 16:
        try:
            commands = [
            "service tomcat start"
            "service mongod start"
            "service postgresql-11 start"
            ]
            manage_services(commands)
        except subprocess.CalledProcessError:
            logger.error("Failed to start services.")
            sys.exit(1)
        save_progress(16)
    
    # Final
    logger.info("Migration process completed successfully.")
if __name__ == "__main__":
    main()
