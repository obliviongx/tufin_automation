import os
import subprocess
import json
from getpass import getpass, getuser
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_command(command):
    log_dir = "/opt/script_migration_st/" 
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "migration_st_logfile.txt")
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, encoding='utf-8')
        with open("log_file_path", "a") as logfile:
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
    if response == 'n':
        logger.info("Process cancelled by user.")
        sys.exit(0)
    elif response == 'y' or response == '':
        return True
    else:
        logger.warning("Invalid response. Please enter 'Y' or press 'Enter' to continue, or 'N' to cancel.")
        return ask_user(question)

def manage_services(commands):
    for command in commands:
        run_command(command.split())

from datetime import datetime

def create_backup_file():
    logger.info("Creating Backup File")
    output = run_command(["screen", "-dmS", "finalTransfer"])
    output += run_command(["tos", "backup", "--st", "--conf-only", "config"])
    # generate filename based on current date
    backup_file = "config_" + datetime.now().strftime("%Y_%m_%d") + ".zip"
    return backup_file

def main():
    current_step = load_progress()
    backup_file = None
    if current_step is not None:
        logger.info(f"Resuming from step {current_step + 1}")
    else:
        logger.info("Starting from the beginning")
    
    # Step 1: Check PostgreSQL version
    if current_step is None or current_step < 1:
        try:
            run_command(["psql", "-V"])
        except subprocess.CalledProcessError:
            logger.error("Failed to check PostgreSQL version.")
            sys.exit(1)
        save_progress(1)
    
    # Step 2: Check license count
    if current_step is None or current_step < 2:
        try:
            output = run_command(["psql", "securetrack", "-Upostgres", "-c", "select count(*) from st_licenses"])
            if "1" not in output:
                logger.warning("You have an Invalid EVAL license or invalid license")
                if ask_user("Would you like to delete the EVAL license? (yes/no)"):
                    run_command(["psql", "securetrack", "-Upostgres", "-c", "delete from st_licenses where license_type='evaluation'"])
                    save_progress(2)
        except subprocess.CalledProcessError:
            logger.error("Failed to check license count.")
            sys.exit(1)
        save_progress(2)
    # Step 3: Check TOS version
    if current_step is None or current_step < 3:
        try:
            run_command(["tos", "version"])
            save_progress(3)
        except subprocess.CalledProcessError:
            logger.error("Failed to check TOS version.")
            sys.exit(1)
        save_progress(3)
    # Step 4: Check Red Hat version
    if current_step is None or current_step < 4:
        try:
            run_command(["cat", "/etc/redhat-release"])
        except subprocess.CalledProcessError:
            logger.error("Failed to check Red Hat version.")
            sys.exit(1)
        save_progress(4)
    
    # Step 5: Create new screen session
    if current_step is None or current_step < 5:
        try:
            run_command(["screen", "-dmS", "PreliminaryTransfer"])
            save_progress(5)
        except subprocess.CalledProcessError:
            logger.error("Failed to create new screen session.")
            sys.exit(1)
        save_progress(5)
    
    # Step 6: Run rsync 1 
    if current_step is None or current_step < 6:
        username = getuser()
        ip = input("Please enter your IP address: ")
        password = getpass("Please enter your SSH password: ")
        try:
            run_command(["rsync", "-avzhe", "--progress", f"sshpass -p '{password}'", "ssh", "-o", "StrictHostKeyChecking=no",
                "/var/lib/pgsql/11/data/", f"{username}@{ip}:/opt/tufin/data/volumes/postgres/11/data/", "--rsync-path=sudo rsync"])
        except subprocess.CalledProcessError:
            logger.error("Failed to run rsync.")
            sys.exit(1)
        save_progress(6)
    
    # Step 7: Create Backup File
    if current_step is None or current_step < 7:
        try:
            backup_file = create_backup_file()
            save_progress(7)
        except subprocess.CalledProcessError:
            logger.error("Failed to Create Backup.")
            sys.exit(1)
        save_progress(7)
    
    # Step 8: Transfer Backup File
    if current_step is None or current_step < 8:
        username = getuser()
        ip = input("Please enter your IP address: ")
        password = getpass("Please enter your SSH password: ")
        try:
            run_command(["rsync", "-avzhe", "--progress", f"sshpass -p '{password}'", "ssh", "-o", "StrictHostKeyChecking=no",
                backup_file, f"{username}@{ip}:/opt/tufin/migration/backup.zip", "--rsync-path=sudo rsync"])
            save_progress(8)
        except subprocess.CalledProcessError:
            logger.error("Failed to run rsync for Backup.")
            sys.exit(1)
        save_progress(8)
    
    # Step 9: Stop Services
    if current_step is None or current_step < 9:
        try:
            commands = [
                "st shutdown",
                "systemctl stop crond",
                "systemctl stop mongod",
                "systemctl stop postgresql-11",
                "systemctl stop ldap-cache",
                "systemctl stop commit-manager",
                "systemctl stop device-comm",
                "systemctl stop fqdn-cache",
                "systemctl stop tufin-topology",
                "systemctl stop keycloak",
                "systemctl stop tufin-jobs",
                "systemctl stop tomcat",
                "systemctl stop jms",
            ]
            manage_services(commands)
        except subprocess.CalledProcessError:
            logger.error("Failed to stop services.")
            sys.exit(1)
        save_progress(9)
    
    # Step 10: Run Rsync 2
    if current_step is None or current_step < 10:
        try:
            run_command(["rsync", "-avzhe", "--progress", f"sshpass -p '{password}'", "ssh", "-o", "StrictHostKeyChecking=no",
                "/var/lib/pgsql/11/data/", f"{username}@{ip}:/opt/tufin/data/volumes/postgres/11/data/", "--rsync-path=sudo rsync"])
            save_progress(10)
        except subprocess.CalledProcessError:
            logger.error("Failed to start transfer.")
            sys.exit(1)
        save_progress(10)    
    
    # Step 11: Start Services
    if current_step is None or current_step < 11:
        try:
            commands = [
                "st shutdown",
                "systemctl start crond",
                "systemctl start mongod",
                "systemctl start postgresql-11",
                "systemctl start ldap-cache",
                "systemctl start commit-manager",
                "systemctl start device-comm",
                "systemctl start fqdn-cache",
                "systemctl start tufin-topology",
                "systemctl start keycloak",
                "systemctl start tufin-jobs",
                "systemctl start tomcat",
                "systemctl start jms",
            ]
            manage_services(commands)
        except subprocess.CalledProcessError:
            logger.error("Failed to stop services.")
            sys.exit(1)
        save_progress(11)
    
    # Final
    logger.info("Secure Track process completed successfully.")
    if __name__ == "__main__":
        main()