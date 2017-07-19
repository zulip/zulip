#!/bin/bash

if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ]; then
    set -x
    set -o functrace
fi
set -e

if [ -f /opt/docker-functions.sh ]; then
    source /opt/docker-functions.sh
elif [ -f ./docker-functions.sh ]; then
    source /opt/docker-functions.sh
else
    echo "docker-functions.sh not found in /opt nor current work directory."
    exit 1
fi

# BEGIN app functions
app_run() {
    run_initial_configuration
    bootstrap_environment
    echo "=== Begin Run Phase ==="
    echo "Starting Zulip using supervisor with \"/etc/supervisor/supervisord.conf\" config ..."
    echo ""
    exec supervisord -n -c "/etc/supervisor/supervisord.conf"
}
app_managepy() {
    COMMAND="$1"
    shift 1
    if [ -z "$COMMAND" ]; then
        echo "No command given for manage.py. Defaulting to \"shell\"."
        COMMAND="shell"
    fi
    echo "Running manage.py ..."
    set +e
    exec su zulip -c "/home/zulip/deployments/current/manage.py $COMMAND $*"
}
app_backup() {
    echo "Starting backup process ..."
    if [ -d "/tmp/backup-$(date "%D-%H-%M-%S")" ]; then
        echo "Temporary backup folder for \"$(date "%D-%H-%M-%S")\" already exists. Aborting."
        echo "Backup process failed. Exiting."
        exit 1
    fi
    local BACKUP_FOLDER
    BACKUP_FOLDER="/tmp/backup-$(date "%D-%H-%M-%S")"
    mkdir -p "$BACKUP_FOLDER"
    wait_for_database
    pg_dump -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_USER" "$DB_NAME" > "$BACKUP_FOLDER/database-postgres.sql"
    tar -zcvf "$DATA_DIR/backups/backup-$(date "%D-%H-%M-%S").tar.gz" "$BACKUP_FOLDER/"
    rm -r "${BACKUP_FOLDER:?}/"
    echo "Backup process succeeded."
    exit 0
}
app_restore() {
    echo "Starting restore process ..."
    if [ "$(ls -A "$DATA_DIR/backups/")" ]; then
        echo "No backups to restore found in \"$DATA_DIR/backups/\"."
        echo "Restore process failed. Exiting."
        exit 1
    fi
    while true; do
        ls "$DATA_DIR/backups/" | awk '{print "|-> " $1}'
        echo "Please enter backup filename (full filename with extension): "
        read BACKUP_FILE
        if [ -z "$BACKUP_FILE" ]; then
            echo "Empty filename given. Please try again."
            echo ""
            continue
        fi
        if [ ! -e "$DATA_DIR/backups/$BACKUP_FILE" ]; then
            echo "File \"$BACKUP_FILE\" not found. Please try again."
            echo ""
        fi
        break
    done
    echo "File \"$BACKUP_FILE\" found."
    echo ""
    echo "==============================================================="
    echo "!! WARNING !! Your current data will be deleted!"
    echo "!! WARNING !! YOU HAVE BEEN WARNED! You can abort with \"CTRL+C\"."
    echo "!! WARNING !! Waiting 10 seconds before continuing ..."
    echo "==============================================================="
    echo ""
    local TIMEOUT=11
    while true; do
        TIMEOUT=$(expr $TIMEOUT - 1)
        if [[ $TIMEOUT -eq 0 ]]; then
            break
        fi
        echo "$TIMEOUT"
        sleep 1
    done
    echo "!! WARNING !! Starting restore process ... !! WARNING !!"
    wait_for_database
    tar -zxvf "$DATA_DIR/backups/$BACKUP_FILE" -C /tmp
    psql -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_USER" "$DB_NAME" < "/tmp/$(basename "$BACKUP_FILE" | cut -d. -f1)/database-postgres.sql"
    rm -r "/tmp/$(basename  | cut -d. -f1)/"
    echo "Restore process succeeded. Exiting."
    exit 0
}
app_certs() {
    configure_certs
}
app_help() {
    echo "Available commands:"
    echo "> app:help     - Show this help menu and exit"
    echo "> app:version  - Container Zulip server version"
    echo "> app:managepy - Run Zulip's manage.py script (defaults to \"shell\")"
    echo "> app:backup   - Create backups of Zulip instances"
    echo "> app:restore  - Restore backups of Zulip instances"
    echo "> app:certs    - Create self-signed certificates"
    echo "> app:run      - Run the Zulip server"
    echo "> [COMMAND]    - Run given command with arguments in shell"
}
app_version() {
    echo "This container contains:"
    echo "> Zulip server $ZULIP_VERSION"
    echo "> Checksum: $ZULIP_CHECKSUM"
    exit 0
}
# END app functions

case "$1" in
    app:run)
        app_run
    ;;
    app:managepy)
        shift 1
        app_managepy "$@"
    ;;
    app:backup)
        app_backup
    ;;
    app:restore)
        app_restore
    ;;
    app:certs)
        app_certs
    ;;
    app:help)
        app_help
    ;;
    app:version)
        app_version
    ;;
    *)
        if [[ -x $1 ]]; then
            $1
        else
            COMMAND="$1"
            if [[ -n $(which $COMMAND) ]] ; then
                shift 1
                exec "$(which $COMMAND)" "$@"
            else
                app_help
            fi
        fi
    ;;
esac
