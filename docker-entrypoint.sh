#!/bin/bash

if [ "$DEBUG" == "true" ] || [ "$DEBUG" == "True" ]; then
    set -x
    set -o functrace
fi
set -e

# DB aka Database
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_HOST_PORT="${DB_HOST_PORT:-5432}"
DB_NAME="${DB_NAME:-zulip}"
DB_SCHEMA="${DB_SCHEMA:-zulip}"
DB_USER="${DB_USER:-zulip}"
DB_PASS="${DB_PASS:-zulip}"
DB_ROOT_USER="${DB_ROOT_USER:-postgres}"
DB_ROOT_PASS="${DB_ROOT_PASS:-$(echo $DB_PASS)}"
unset DB_PASSWORD
# RabbitMQ
IGNORE_RABBITMQ_ERRORS="false"
SETTING_RABBITMQ_HOST="${SETTING_RABBITMQ_HOST:-127.0.0.1}"
SETTING_RABBITMQ_USER="${SETTING_RABBITMQ_USER:-zulip}"
SETTING_RABBITMQ_PASSWORD="${SETTING_RABBITMQ_PASSWORD:-zulip}"
SECRETS_rabbitmq_password="${SECRETS_rabbitmq_password:-$(echo $SETTING_RABBITMQ_PASSWORD)}"
unset SETTING_RABBITMQ_PASSWORD
# Redis
SETTING_RATE_LIMITING="${SETTING_RATE_LIMITING:-True}"
SETTING_REDIS_HOST="${SETTING_REDIS_HOST:-127.0.0.1}"
SETTING_REDIS_PORT="${SETTING_REDIS_PORT:-6379}"
# Memcached
if [ -z "$SETTING_MEMCACHED_LOCATION" ]; then
    SETTING_MEMCACHED_LOCATION="127.0.0.1:11211"
fi
# Nginx settings
DISABLE_HTTPS="${DISABLE_HTTPS:-false}"
NGINX_WORKERS="${NGINX_WORKERS:-2}"
NGINX_PROXY_BUFFERING="${NGINX_PROXY_BUFFERING:-off}"
NGINX_MAX_UPLOAD_SIZE="${NGINX_MAX_UPLOAD_SIZE:-24m}"
# Zulip certifcate parameters
ZULIP_AUTO_GENERATE_CERTS="${ZULIP_AUTO_GENERATE_CERTS:-True}"
ZULIP_CERTIFICATE_SUBJ="${ZULIP_CERTIFICATE_SUBJ:-}"
ZULIP_CERTIFICATE_C="${ZULIP_CERTIFICATE_C:-US}"
ZULIP_CERTIFICATE_ST="${ZULIP_CERTIFICATE_ST:-Denial}"
ZULIP_CERTIFICATE_L="${ZULIP_CERTIFICATE_L:-Springfield}"
ZULIP_CERTIFICATE_O="${ZULIP_CERTIFICATE_O:-Dis}"
ZULIP_CERTIFICATE_CN="${ZULIP_CERTIFICATE_CN:-}"
# Zulip related settings
ZULIP_AUTH_BACKENDS="${ZULIP_AUTH_BACKENDS:-EmailAuthBackend}"
ZULIP_RUN_POST_SETUP_SCRIPTS="${ZULIP_RUN_POST_SETUP_SCRIPTS:-True}"
# Zulip user setup
FORCE_FIRST_START_INIT="${FORCE_FIRST_START_INIT:-False}"
export ZULIP_USER_CREATION_ENABLED="${ZULIP_USER_CREATION_ENABLED:-True}"
export ZULIP_USER_FULLNAME="${ZULIP_USER_FULLNAME:-Zulip Docker}"
export ZULIP_USER_DOMAIN="${ZULIP_USER_DOMAIN:-$(echo $SETTING_EXTERNAL_HOST)}"
export ZULIP_USER_EMAIL="${ZULIP_USER_EMAIL:-}"
export ZULIP_USER_PASS="${ZULIP_USER_PASS:-zulip}"
# Auto backup settings
AUTO_BACKUP_ENABLED="${AUTO_BACKUP_ENABLED:-True}"
AUTO_BACKUP_INTERVAL="${AUTO_BACKUP_INTERVAL:-30 3 * * *}"
# Zulip configuration function specific variable(s)
SPECIAL_SETTING_DETECTION_MODE="${SPECIAL_SETTING_DETECTION_MODE:-True}"
# entrypoint.sh specific variable(s)
ZPROJECT_SETTINGS="/home/zulip/deployments/current/zproject/settings.py"
SETTINGS_PY="/etc/zulip/settings.py"

# BEGIN appRun functions
# === initialConfiguration ===
prepareDirectories() {
    if [ ! -d "$DATA_DIR" ]; then
        mkdir -p "$DATA_DIR"
    fi
    if [ ! -d "$DATA_DIR/backups" ]; then
        echo "Creating backups folder ..."
        mkdir -p "$DATA_DIR/backups"
        echo "Created backups folder."
    fi
    if [ ! -d "$DATA_DIR/certs" ]; then
        echo "Creating certs folder ..."
        mkdir -p "$DATA_DIR/certs"
        echo "Created certs folder."
    fi
    if [ ! -d "$DATA_DIR/uploads" ]; then
        echo "Creating uploads folder ..."
        mkdir -p "$DATA_DIR/uploads"
        echo "Created uploads folder."
    fi
    echo "Preparing and linking the uploads folder ..."
    rm -rf /home/zulip/uploads
    ln -sfT "$DATA_DIR/uploads" /home/zulip/uploads
    chown zulip:zulip -R "$DATA_DIR/uploads"
    # Create settings directories
    if [ ! -d "$DATA_DIR/settings" ]; then
        mkdir -p "$DATA_DIR/settings"
    fi
    # Link settings folder
    if [ ! -d "$DATA_DIR/settings/etc-zulip" ]; then
        cp -rf /etc/zulip "$DATA_DIR/settings/etc-zulip"
    else
        if [ -h "$DATA_DIR/settings/etc-zulip" ]; then
            rm -rf "$DATA_DIR/settings/etc-zulip"
        fi
    fi
    # Link /etc/zulip/ settings folder
    rm -rf /etc/zulip
    ln -sfT "$DATA_DIR/settings/etc-zulip" /etc/zulip
    echo "Prepared and linked the uploads directory."
}
setConfigurationValue() {
    if [ -z "$1" ]; then
        echo "No KEY given for setConfigurationValue."
        return 1
    fi
    if [ -z "$3" ]; then
        echo "No FILE given for setConfigurationValue."
        return 1
    fi
    local KEY="$1"
    local VALUE
    local FILE="$3"
    local TYPE="$4"
    if [ -z "$TYPE" ]; then
        case "$2" in
            [Tt][Rr][Uu][Ee]|[Ff][Aa][Ll][Ss][Ee]|[Nn]one)
            TYPE="bool"
            ;;
            [0-9]*)
            TYPE="integer"
            ;;
            \(*\))
            TYPE="array"
            ;;
            *)
            TYPE="string"
            ;;
        esac
    fi
    case "$TYPE" in
        emptyreturn)
        if [ -z "$2" ]; then
            return 0
        fi
        ;;
        literal)
        VALUE="$1"
        ;;
        bool|boolean|int|integer|array)
        VALUE="$KEY = $2"
        ;;
        string|*)
        VALUE="$KEY = '${2//\'/\'}'"
        ;;
    esac
    echo "$VALUE" >> "$FILE"
    echo "Setting key \"$KEY\", type \"$TYPE\" in file \"$FILE\"."
}
nginxConfiguration() {
    echo "Executing nginx configuration ..."
    if [ "$DISABLE_HTTPS" == "True" ] || [ "$DISABLE_HTTPS" == "true" ]; then
        echo "Disabling https in nginx."
        mv -f /opt/files/nginx/zulip-enterprise-http /etc/nginx/sites-enabled/zulip-enterprise
    fi
    sed -i "s/worker_processes .*/worker_processes $NGINX_WORKERS;/g" /etc/nginx/nginx.conf
    sed -i "s/client_max_body_size .*/client_max_body_size $NGINX_MAX_UPLOAD_SIZE;/g" /etc/nginx/nginx.conf
    sed -i "s/proxy_buffering .*/proxy_buffering $NGINX_PROXY_BUFFERING;/g" /etc/nginx/zulip-include/proxy_longpolling
    echo "Nginx configuration succeeded."
}
configureCerts() {
    echo "Exectuing certificates configuration..."
    if [ "$DISABLE_HTTPS" == "True" ] || [ "$DISABLE_HTTPS" == "true" ]; then
        echo "DISABLE_HTTPS is true. No certs required."
        return 0
    fi
    case "$ZULIP_AUTO_GENERATE_CERTS" in
        [Tt][Rr][Uu][Ee])
            ZULIP_AUTO_GENERATE_CERTS="True"
        ;;
        [Ff][Aa][Ll][Ss][Ee])
            ZULIP_AUTO_GENERATE_CERTS="False"
        ;;
        *)
            echo "Defaulting \"ZULIP_AUTO_GENERATE_CERTS\" to \"True\". Couldn't parse if \"True\" or \"False\"."
            ZULIP_AUTO_GENERATE_CERTS="True"
        ;;
    esac
    if [ ! -e "$DATA_DIR/certs/zulip.key" ] && [ ! -e "$DATA_DIR/certs/zulip.combined-chain.crt" ]; then
        if [ ! -z "$ZULIP_AUTO_GENERATE_CERTS" ] && ([ "$ZULIP_AUTO_GENERATE_CERTS" == "True" ] || [ "$ZULIP_AUTO_GENERATE_CERTS" == "true" ]); then
            echo "No certs in \"$DATA_DIR/certs\"."
            echo "Autogenerating certificates ..."
            if [ -z "$ZULIP_CERTIFICATE_SUBJ" ]; then
                if [ -z "$ZULIP_CERTIFICATE_CN" ]; then
                    if [ -z "$SETTING_EXTERNAL_HOST" ]; then
                        echo "Certificates generation failed. \"ZULIP_CERTIFICATE_CN\" and as fallback \"SETTING_EXTERNAL_HOST\" not given."
                        echo "Certificates configuration failed."
                        exit 1
                    fi
                    ZULIP_CERTIFICATE_CN="$SETTING_EXTERNAL_HOST"
                fi
                ZULIP_CERTIFICATE_SUBJ="/C=$ZULIP_CERTIFICATE_C/ST=$ZULIP_CERTIFICATE_ST/L=$ZULIP_CERTIFICATE_L/O=$ZULIP_CERTIFICATE_O/CN=$ZULIP_CERTIFICATE_CN"
            fi
            openssl genrsa -des3 -passout pass:x -out /tmp/server.pass.key 4096
            openssl rsa -passin pass:x -in /tmp/server.pass.key -out "$DATA_DIR/certs/zulip.key"
            openssl req -new -nodes -subj "$ZULIP_CERTIFICATE_SUBJ" -key "$DATA_DIR/certs/zulip.key" -out /tmp/server.csr
            openssl x509 -req -days 365 -in /tmp/server.csr -signkey "$DATA_DIR/certs/zulip.key" -out "$DATA_DIR/certs/zulip.combined-chain.crt"
            rm -f /tmp/server.csr /tmp/server.pass.key
            echo "Certificate autogeneration succeeded."
        else
            echo "Certificates already exist. No need to generate them. Continuing."
        fi
    fi
    if [ ! -e "$DATA_DIR/certs/zulip.key" ]; then
        echo "No zulip.key given in $DATA_DIR."
        echo "Certificates configuration failed."
        exit 1
    fi
    if [ ! -e "$DATA_DIR/certs/zulip.combined-chain.crt" ]; then
        echo "No zulip.combined-chain.crt given in $DATA_DIR."
        echo "Certificates configuration failed."
        exit 1
    fi
    ln -sfT "$DATA_DIR/certs/zulip.key" /etc/ssl/private/zulip.key
    ln -sfT "$DATA_DIR/certs/zulip.combined-chain.crt" /etc/ssl/certs/zulip.combined-chain.crt
    echo "Certificates configuration succeeded."
}
secretsConfiguration() {
    echo "Setting Zulip secrets ..."
    if [ ! -e "/etc/zulip/zulip-secrets.conf" ]; then
        echo "Generating Zulip secrets ..."
        /root/zulip/scripts/setup/generate_secrets.py
        echo "Secrets generation succeeded."
    else
        echo "Secrets already generated."
    fi
    set +e
    local SECRETS=($(env | sed -nr "s/SECRETS_([0-9A-Z_a-z-]*).*/\1/p"))
    for SECRET_KEY in "${SECRETS[@]}"; do
        local KEY="SECRETS_$SECRET_KEY"
        local SECRET_VAR="${!KEY}"
        if [ -z "$SECRET_VAR" ]; then
            echo "Empty secret for key \"$SECRET_KEY\"."
            continue
        fi
        grep -q "$SECRET_KEY" /etc/zulip/zulip-secrets.conf
        if (($? > 0)); then
            echo "$SECRET_KEY = $SECRET_VAR" >> /etc/zulip/zulip-secrets.conf
            echo "Secret added for \"$SECRET_KEY\"."
        else
            sed -i -r "s~#?$SECRET_KEY[ ]*=.*~$SECRET_KEY = $SECRET_VAR~g" /etc/zulip/zulip-secrets.conf
            echo "Secret found for \"$SECRET_KEY\"."
        fi
    done
    set -e
    unset SECRET_KEY SECRET_VAR KEY
    echo "Zulip secrets configuration succeeded."
}
databaseConfiguration() {
    echo "Setting database configuration ..."
    local VALUE="{
  'default': {
    'ENGINE': 'django.db.backends.postgresql_psycopg2',
    'NAME': '$DB_NAME',
    'USER': '$DB_USER',
    'PASSWORD': '$DB_PASS',
    'HOST': '$DB_HOST',
    'PORT': '$DB_HOST_PORT',
    'SCHEMA': '$DB_SCHEMA',
    'CONN_MAX_AGE': 600,
    'OPTIONS': {
        'connection_factory': TimeTrackingConnection,
        'sslmode': 'prefer',
    },
  },
}"
    setConfigurationValue "DATABASES" "$VALUE" "$ZPROJECT_SETTINGS" "array"
    echo "Database configuration succeeded."
}
authenticationBackends() {
    echo "Activating authentication backends ..."
    local FIRST=true
    echo "$ZULIP_AUTH_BACKENDS" | sed -n 1'p' | tr ',' '\n' | while read AUTH_BACKEND; do
        if [ "$FIRST" = true ]; then
            setConfigurationValue "AUTHENTICATION_BACKENDS" "('zproject.backends.${AUTH_BACKEND//\'/\'}',)" "$SETTINGS_PY" "array"
            FIRST=false
        else
            setConfigurationValue "AUTHENTICATION_BACKENDS += ('zproject.backends.${AUTH_BACKEND//\'/\'}',)" "" "$SETTINGS_PY" "literal"
        fi
        echo "Adding authentication backend \"$AUTH_BACKEND\"."
    done
    echo "Authentication backend activation succeeded."
}
zulipConfiguration() {
    echo "Executing Zulip configuration ..."
    if [ ! -z "$ZULIP_CUSTOM_SETTINGS" ]; then
        echo -e "\n$ZULIP_CUSTOM_SETTINGS" >> "$ZPROJECT_SETTINGS"
    fi
    local given_settings=($(env | sed -n -r "s/SETTING_([0-9A-Za-z_]*).*/\1/p"))
    for setting_key in "${given_settings[@]}"; do
        local key="SETTING_$setting_key"
        local setting_var="${!key}"
        local file="$ZPROJECT_SETTINGS"
        local type="string"
        if [ -z "$setting_var" ]; then
            echo "Empty var for key \"$setting_key\"."
            continue
        fi
        # Zulip settings.py / zproject specific overrides here
        if [ "$setting_key" = "ADMIN_DOMAIN" ] || [ "$setting_key" = "MEMCACHED_LOCATION" ] || \
            [[ "$setting_key" = RABBITMQ* ]] || [[ "$setting_key" = REDIS* ]] || \
            [ "$setting_key" = "RATE_LIMITING" ] || [ "$setting_key" = "EXTERNAL_HOST" ] || \
            [ "$setting_key" = "ZULIP_ADMINISTRATOR" ] || [ "$setting_key" = "ADMIN_DOMAIN" ] || \
            [ "$setting_key" = "SECRET_KEY" ] || [ "$setting_key" = "NOREPLY_EMAIL_ADDRESS" ] || \
            [ "$setting_key" = "DEFAULT_FROM_EMAIL" ] || [ "$setting_key" = "ALLOWED_HOSTS" ] || \
            [[ "$setting_key" = AUTH_* ]] || [[ "$setting_key" = LDAP_* ]]; then
            file="$SETTINGS_PY"
        fi
        if [ "$setting_key" = "AUTH_LDAP_USER_SEARCH" ] || [ "$setting_key" = "AUTH_LDAP_USER_ATTR_MAP" ] || \
           ([ "$setting_key" = "LDAP_APPEND_DOMAIN" ] && [ "$setting_var" = "None" ]) && [ "$setting_key" = "SECURE_PROXY_SSL_HEADER" ] || \
           [[ "$setting_key" = "CSRF_"* ]] || [[ "$setting_key" = "ALLOWED_HOSTS" ]]; then
            type="array"
        fi
        if [ -z "$SPECIAL_SETTING_DETECTION_MODE" ] && ([ "$SPECIAL_SETTING_DETECTION_MODE" = "True" ] || [ "$SPECIAL_SETTING_DETECTION_MODE" = "true" ]); then
            type=""
        fi
        setConfigurationValue "$setting_key" "$setting_var" "$file" "$type"
    done
    unset setting_key setting_var KEY
    su zulip -c "/home/zulip/deployments/current/manage.py checkconfig"
    if [[ $? != 0 ]]; then
        echo "Error in Zulip configuration. Exiting."
        exit 1
    fi
    echo "Zulip configuration succeeded."
}
autoBackupConfiguration() {
    if ([ "$AUTO_BACKUP_ENABLED" != "True" ] && [ "$AUTO_BACKUP_ENABLED" != "true" ]); then
        rm -f /etc/cron.d/autobackup
        echo "Auto backup is disabled. Continuing."
        return 0
    fi
    echo "MAILTO=""\n$AUTO_BACKUP_INTERVAL cd /;/entrypoint.sh app:backup" > /etc/cron.d/autobackup
    echo "Auto backup enabled."
}
initialConfiguration() {
    echo "=== Begin Initial Configuration Phase ==="
    prepareDirectories
    nginxConfiguration
    configureCerts
    secretsConfiguration
    databaseConfiguration
    authenticationBackends
    zulipConfiguration
    autoBackupConfiguration
    echo "=== End Initial Configuration Phase ==="
}
# === bootstrappingEnvironment ===
waitingForDatabase() {
    export PGPASSWORD="$DB_PASS"
    local TIMEOUT=60
    echo "Waiting for database server to allow connections ..."
    while ! /usr/bin/pg_isready -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_USER" -t 1 >/dev/null 2>&1
    do
        TIMEOUT=$(expr $TIMEOUT - 1)
        if [[ $TIMEOUT -eq 0 ]]; then
            echo "Could not connect to database server. Exiting."
            unset PGPASSWORD
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    unset PGPASSWORD
}
bootstrapDatabase() {
    echo "(Re)creating database structure ..."
    if [ ! -z "$DB_ROOT_USER" ] && [ ! -z "$DB_ROOT_PASS" ]; then
        echo "Setting up the database, schema and user ..."
        export PGPASSWORD="$DB_ROOT_PASS"
        echo """
        CREATE USER $DB_USER;
        ALTER ROLE $DB_USER SET search_path TO $DB_NAME,public;
        CREATE DATABASE $DB_NAME OWNER=$DB_USER;
        CREATE SCHEMA $DB_SCHEMA AUTHORIZATION $DB_USER;
        """ | psql -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_USER" || :
        echo "Creating tsearch_extras extension ..."
        echo "CREATE EXTENSION tsearch_extras SCHEMA $DB_SCHEMA;" | \
        psql -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_ROOT_USER" "$DB_NAME" || :
        unset PGPASSWORD
        echo "Database structure recreated."
    else
        echo "No database root user nor password given. Not (re)creating database structure."
    fi
}
bootstrapRabbitMQ() {
    echo "Bootstrapping RabbitMQ ..."
    set +e
    /root/zulip/scripts/setup/configure-rabbitmq
    RETURN_CODE=$?
    if [[ $RETURN_CODE != 0 ]] && ([ "$IGNORE_RABBITMQ_ERRORS" != "True" ] && [ "$IGNORE_RABBITMQ_ERRORS" = "true" ]); then
        echo "=> If you want to ignore RabbitMQ bootstrap errors, add the env var 'IGNORE_RABBITMQ_ERRORS' with 'true'."
        echo "Zulip RabbitMQ bootstrap failed in \"configure-rabbitmq\" exit code $RETURN_CODE. Exiting."
        exit $RETURN_CODE
    fi
    set -e
    echo "RabbitMQ bootstrap succeeded."
}
userCreationConfiguration() {
    echo "Executing Zulip user creation script ..."
    if ([ "$ZULIP_USER_CREATION_ENABLED" != "True" ] && [ "$ZULIP_USER_CREATION_ENABLED" != "true" ]) && [ -e "$DATA_DIR/.initiated" ]; then
        rm -f /etc/supervisor/conf.d/zulip_postsetup.conf
        echo "Zulip user creation disabled."
        return 0
    fi
    echo "Zulip user creation left enabled."
}
zulipFirstStartInit() {
    echo "Executing Zulip first start init ..."
    if ([ "$FORCE_FIRST_START_INIT" != "True" ] && [ "$FORCE_FIRST_START_INIT" != "true" ]) && [ -e "$DATA_DIR/.initiated" ]; then
        echo "First Start Init not needed. Continuing."
        return 0
    fi
    local RETURN_CODE=0
    set +e
    su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database
    RETURN_CODE=$?
    if [[ $RETURN_CODE != 0 ]]; then
        echo "Zulip first start database initi failed in \"initialize-database\" exit code $RETURN_CODE. Exiting."
        exit $RETURN_CODE
    fi
    set -e
    touch "$DATA_DIR/.initiated"
    echo "Zulip first start init sucessful."
}
zulipMigration() {
    echo "Migrating Zulip to new version ..."
    set +e
    su zulip -c "/home/zulip/deployments/current/manage.py migrate --noinput"
    local RETURN_CODE=$?
    if [[ $RETURN_CODE != 0 ]]; then
        echo "Zulip migration failed with exit code $RETURN_CODE. Exiting."
        exit $RETURN_CODE
    fi
    set -e
    rm -rf "$DATA_DIR/.zulip-*"
    touch "$DATA_DIR/.zulip-$ZULIP_VERSION"
    echo "Zulip migration succeeded."
}
runPostSetupScripts() {
    echo "Post setup scripts execution ..."
    if ([ "$ZULIP_RUN_POST_SETUP_SCRIPTS" != "True" ] && [ "$ZULIP_RUN_POST_SETUP_SCRIPTS" != "true" ]); then
        echo "Not running post setup scripts. ZULIP_RUN_POST_SETUP_SCRIPTS isn't true."
        return 0
    fi
    if [ ! -d "$DATA_DIR/post-setup.d/" ]; then
        echo "No post-setup.d folder found. Continuing."
        return 0
    fi
    if [ ! "$(ls "$DATA_DIR/post-setup.d/")" ]; then
        echo "No post setup scripts found in \"$DATA_DIR/post-setup.d/\"."
        return 0
    fi
    set +e
    for file in $DATA_DIR/post-setup.d/*; do
        if [ -x "$file" ]; then
            echo "Executing \"$file\" ..."
            bash -c "$file"
            echo "Executed \"$file\". Return code $?."
        else
            echo "Permissions denied for \"$file\". Please check the permissions. Exiting."
            exit 1
        fi
    done
    set -e
    echo "Post setup scripts execution succeeded."
}
bootstrappingEnvironment() {
    echo "=== Begin Bootstrap Phase ==="
    waitingForDatabase
    bootstrapDatabase
    bootstrapRabbitMQ
    userCreationConfiguration
    zulipFirstStartInit
    zulipMigration
    runPostSetupScripts
    echo "=== End Bootstrap Phase ==="
}
# END appRun functionss
appRun() {
    initialConfiguration
    bootstrappingEnvironment
    echo "=== Begin Run Phase ==="
    echo "Starting Zulip using supervisor with \"/etc/supervisor/supervisord.conf\" ..."
    echo ""
    exec supervisord -n -c "/etc/supervisor/supervisord.conf"
}
appManagePy() {
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
appBackup() {
    echo "Starting backup process ..."
    if [ -d "/tmp/backup-$(date "%D-%H-%M-%S")" ]; then
        echo "Temporary backup folder for \"$(date "%D-%H-%M-%S")\" already exists. Aborting."
        echo "Backup process failed. Exiting."
        exit 1
    fi
    local BACKUP_FOLDER
    BACKUP_FOLDER="/tmp/backup-$(date "%D-%H-%M-%S")"
    mkdir -p "$BACKUP_FOLDER"
    waitingForDatabase
    pg_dump -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_USER" "$DB_NAME" > "$BACKUP_FOLDER/database-postgres.sql"
    tar -zcvf "$DATA_DIR/backups/backup-$(date "%D-%H-%M-%S").tar.gz" "$BACKUP_FOLDER/"
    rm -r "${BACKUP_FOLDER:?}/"
    echo "Backup process succeeded."
    exit 0
}
appRestore() {
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
    waitingForDatabase
    tar -zxvf "$DATA_DIR/backups/$BACKUP_FILE" -C /tmp
    psql -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_USER" "$DB_NAME" < "/tmp/$(basename "$BACKUP_FILE" | cut -d. -f1)/database-postgres.sql"
    rm -r "/tmp/$(basename  | cut -d. -f1)/"
    echo "Restore process succeeded. Exiting."
    exit 0
}
appCerts() {
    configureCerts
}
appHelp() {
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
appVersion() {
    echo "This container contains:"
    echo "> Zulip server $ZULIP_VERSION"
    echo "> Checksum: $ZULIP_CHECKSUM"
    exit 0
}

case "$1" in
    app:run)
        appRun
    ;;
    app:managepy)
        shift 1
        appManagePy "$@"
    ;;
    app:backup)
        appBackup
    ;;
    app:restore)
        appRestore
    ;;
    app:certs)
        appCerts
    ;;
    app:help)
        appHelp
    ;;
    app:version)
        appVersion
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
                appHelp
            fi
        fi
    ;;
esac
