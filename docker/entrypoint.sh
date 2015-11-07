#!/bin/bash
# Maintainer Alexander Trost <galexrt@googlemail.com>

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
DB_PASSWORD="${DB_PASSWORD:-zulip}"
DB_PASS="${DB_PASS:-$(echo $DB_PASSWORD)}"
DB_ROOT_USER="${DB_ROOT_USER:-postgres}"
DB_ROOT_PASS="${DB_ROOT_PASS:-$(echo $DB_PASS)}"
unset DB_PASSWORD
# RabbitMQ
RABBITMQ_SETUP="${RABBITMQ_SETUP:-True}"
RABBITMQ_HOST="${RABBITMQ_HOST:-127.0.0.1}"
RABBITMQ_USERNAME="${RABBITMQ_USERNAME:-zulip}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-zulip}"
RABBITMQ_PASS="${RABBITMQ_PASS:-$(echo $RABBITMQ_PASSWORD)}"
export ZULIP_SECRETS_rabbitmq_password="${ZULIP_SECRETS_rabbitmq_password:-$(echo $RABBITMQ_PASS)}"
unset RABBITMQ_PASSWORD RABBITMQ_PASS
# Redis
REDIS_RATE_LIMITING="${REDIS_RATE_LIMITING:-True}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_HOST_PORT="${REDIS_HOST_PORT:-6379}"
# Memcached
MEMCACHED_HOST="${MEMCACHED_HOST:-127.0.0.1}"
MEMCACHED_HOST_PORT="${MEMCACHED_HOST_PORT:-11211}"
MEMCACHED_TIMEOUT="${MEMCACHED_TIMEOUT:-3600}"
# Nginx settings
NGINX_WORKERS="${NGINX_WORKERS:-1}"
NGINX_PROXY_BUFFERING="${NGINX_PROXY_BUFFERING:-off}"
NGINX_MAX_UPLOAD_SIZE="${NGINX_MAX_UPLOAD_SIZE:-20m}"
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
export ZULIP_USER_CREATION_ENABLED="${ZULIP_USER_CREATION_ENABLED:-True}"
export ZULIP_USER_FULLNAME="${ZULIP_USER_FULLNAME:-Zulip Docker}"
export ZULIP_USER_DOMAIN="${ZULIP_USER_DOMAIN:-$(echo $ZULIP_SETTINGS_EXTERNAL_HOST)}"
export ZULIP_USER_EMAIL="${ZULIP_USER_EMAIL:-}"
ZULIP_USER_PASSWORD="${ZULIP_USER_PASSWORD:-zulip}"
export ZULIP_USER_PASS="${ZULIP_USER_PASS:-$(echo $ZULIP_USER_PASSWORD)}"
unset ZULIP_USER_PASSWORD
# Auto backup settings
AUTO_BACKUP_ENABLED="${AUTO_BACKUP_ENABLED:-True}"
AUTO_BACKUP_INTERVAL="${AUTO_BACKUP_INTERVAL:-30 3 * * *}"

# entrypoint.sh specific variables
ZULIP_CURRENT_DEPLOY="/home/zulip/deployments/current"
ZPROJECT_SETTINGS="$ZULIP_CURRENT_DEPLOY/zproject/settings.py"
ZULIP_SETTINGS="/etc/zulip/settings.py"

# BEGIN appRun functions
# === initialConfiguration ===
prepareDirectories() {
    if [ ! -d "$DATA_DIR/backups" ]; then
        mkdir -p "$DATA_DIR/backups" || :
    fi
    if [ ! -d "$DATA_DIR/certs" ]; then
        mkdir -p "$DATA_DIR/certs" || :
    fi
    if [ ! -d "$DATA_DIR/uploads" ]; then
        mkdir -p "$DATA_DIR/uploads" || :
        if [ -d /home/zulip/uploads ]; then
            mv -f /home/zulip/uploads "$DATA_DIR/uploads"
        else
            mkdir -p /home/zulip/uploads || :
        fi
    else
        rm -rf /home/zulip/uploads
    fi
    ln -sfT "$DATA_DIR/uploads" /home/zulip/uploads
    chown zulip:zulip -R "$DATA_DIR/uploads"
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
            [Tt][Rr][Uu][Ee]|[Ff][Aa][Ll][Ss][Ee])
            TYPE="bool"
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
    echo "Setting key \"$KEY\", type \"$TYPE\"."
}
nginxConfiguration() {
    echo "Executing nginx configuration ..."
    sed -i "s/worker_processes .*/worker_processes $NGINX_WORKERS;/g" /etc/nginx/nginx.conf
    sed -i "s/client_max_body_size .*/client_max_body_size $NGINX_MAX_UPLOAD_SIZE;/g" /etc/nginx/nginx.conf
    sed -i "s/proxy_buffering .*/proxy_buffering $NGINX_PROXY_BUFFERING;/g" /etc/nginx/zulip-include/proxy_longpolling
    echo "Nginx configuration succeeded."
}
configureCerts() {
    echo "Exectuing certificates configuration..."
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
                    if [ -z "$ZULIP_SETTINGS_EXTERNAL_HOST" ]; then
                        echo "Certificates generation failed. \"ZULIP_CERTIFICATE_CN\" and as fallback \"ZULIP_SETTINGS_EXTERNAL_HOST\" not given."
                        echo "Certificates configuration failed."
                        exit 1
                    fi
                    ZULIP_CERTIFICATE_CN="$ZULIP_SETTINGS_EXTERNAL_HOST"
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
    if [ ! -e "$DATA_DIR/zulip-secrets.conf" ]; then
        echo "Generating Zulip secrets ..."
        /root/zulip/scripts/setup/generate_secrets.py
        mv -f /etc/zulip/zulip-secrets.conf "$DATA_DIR/zulip-secrets.conf"
        echo "Secrets generation succeeded."
    else
        rm -rf /etc/zulip/zulip-secrets.con
        echo "Secrets already generated."
    fi
    ln -sfT "$DATA_DIR/zulip-secrets.conf" /etc/zulip/zulip-secrets.conf
    set +e
    local SECRETS=($(env | sed -nr "s/ZULIP_SECRETS_([A-Z_a-z-]*).*/\1/p"))
    for SECRET_KEY in "${SECRETS[@]}"; do
        local KEY="ZULIP_SECRETS_$SECRET_KEY"
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
    sed -i "s~psycopg2.connect\(.*\)~psycopg2.connect(\"host=$DB_HOST port=$DB_HOST_PORT dbname=$DB_NAME user=$DB_USER password=$DB_PASS\")~g" /usr/local/bin/process_fts_updates
    echo "Database configuration succeeded."
}
cacheRatelimitConfiguration() {
    echo "Setting caches configuration ..."
    local VALUE="{
    'default': {
        'BACKEND':  'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': '$MEMCACHED_HOST:$MEMCACHED_HOST_PORT',
        'TIMEOUT':  $MEMCACHED_TIMEOUT
    },
    'database': {
        'BACKEND':  'django.core.cache.backends.db.DatabaseCache',
        'LOCATION':  'third_party_api_results',
        'TIMEOUT': 2000000000,
        'OPTIONS': {
            'MAX_ENTRIES': 100000000,
            'CULL_FREQUENCY': 10,
        }
    },
}"
    setConfigurationValue "CACHES" "$VALUE" "$ZPROJECT_SETTINGS" "array"
    echo "Caches configuration succeeded."
}
authenticationBackends() {
    echo "Activating authentication backends ..."
    local FIRST=true
    echo "$ZULIP_AUTH_BACKENDS" | sed -n 1'p' | tr ',' '\n' | while read AUTH_BACKEND; do
        if [ "$FIRST" = true ]; then
            setConfigurationValue "AUTHENTICATION_BACKENDS" "('zproject.backends.${AUTH_BACKEND//\'/\'}',)" "$ZULIP_SETTINGS" "array"
            FIRST=false
        else
            setConfigurationValue "AUTHENTICATION_BACKENDS += ('zproject.backends.${AUTH_BACKEND//\'/\'}',)" "" "$ZULIP_SETTINGS" "literal"
        fi
        echo "Adding authentication backend \"$AUTH_BACKEND\"."
    done
    echo "Authentication backend activation succeeded."
}
redisConfiguration() {
    echo "Setting redis configuration ..."
    setConfigurationValue "RATE_LIMITING" "$REDIS_RATE_LIMITING" "$ZPROJECT_SETTINGS" "bool"
    setConfigurationValue "REDIS_HOST" "$REDIS_HOST" "$ZPROJECT_SETTINGS"
    setConfigurationValue "REDIS_HOST_PORT" "$REDIS_HOST_PORT" "$ZPROJECT_SETTINGS" "int"
    echo "Redis configuration succeeded."
}
rabbitmqConfiguration() {
    echo "Setting rabbitmq configuration ..."
    setConfigurationValue "RABBITMQ_HOST" "$RABBITMQ_HOST" "$ZPROJECT_SETTINGS"
    sed -i "s~pika.ConnectionParameters('localhost',~pika.ConnectionParameters(settings.RABBITMQ_HOST,~g" "$ZULIP_CURRENT_DEPLOY/zerver/lib/queue.py"
    setConfigurationValue "RABBITMQ_USERNAME" "$RABBITMQ_USERNAME" "$ZPROJECT_SETTINGS"
    echo "Rabbitmq configuration succeeded."
}
camoConfiguration() {
    setConfigurationValue "CAMO_URI" "$CAMO_URI" "$ZPROJECT_SETTINGS" "emptyreturn"
}
zulipConfiguration() {
    echo "Executing Zulip configuration ..."
    if [ ! -z "$ZULIP_CUSTOM_SETTINGS" ]; then
        echo -e "\n$ZULIP_CUSTOM_SETTINGS" >> "$ZPROJECT_SETTINGS"
    fi
    local SET_SETTINGS=($(env | sed -n -r "s/ZULIP_SETTINGS_([A-Z_]*).*/\1/p"))
    for SETTING_KEY in "${SET_SETTINGS[@]}"; do
        local KEY="ZULIP_SETTINGS_$SETTING_KEY"
        local SETTING_VAR="${!KEY}"
        if [ -z "$SETTING_VAR" ]; then
            echo "Empty var for key \"$SETTING_KEY\"."
            continue
        fi
        setConfigurationValue "$SETTING_KEY" "$SETTING_VAR" "$ZPROJECT_SETTINGS"
    done
    unset SETTING_KEY SETTING_VAR KEY
    if ! su zulip -c "/home/zulip/deployments/current/manage.py checkconfig"; then
        echo "Error in Zulip configuration."
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
    nginxConfiguration
    configureCerts
    secretsConfiguration
    databaseConfiguration
    cacheRatelimitConfiguration
    authenticationBackends
    redisConfiguration
    rabbitmqConfiguration
    camoConfiguration
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
            echo "Could not connect to database server. Aborting ..."
            exit 1
        fi
        echo -n "."
        sleep 1
    done
}
bootstrapDatabase() {
    echo "(Re)creating database structure ..."
    export PGPASSWORD="$DB_ROOT_PASS"
    if [ ! -z "$DB_ROOT_USER" ] && [ ! -z "$DB_ROOT_PASS" ]; then
        echo "Setting up the database, schema and user ..."
        echo """
        CREATE USER $DB_USER;
        ALTER ROLE $DB_USER SET search_path TO zulip,public;
        CREATE DATABASE $DB_NAME OWNER=$DB_USER;
        CREATE SCHEMA $DB_SCHEMA AUTHORIZATION $DB_USER;
        """ | psql -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_USER" || :
        echo "Creating tsearch_extras extension ..."
        echo "CREATE EXTENSION tsearch_extras SCHEMA $DB_SCHEMA;" | \
        psql -h "$DB_HOST" -p "$DB_HOST_PORT" -U "$DB_ROOT_USER" "$DB_NAME" || :
        echo "Database structure recreated."
    else
        echo "No database root user nor password given. Not (re)creating database structure."
    fi
    unset PGPASSWORD
}
bootstrapRabbitMQ() {
    echo "Bootstrapping RabbitMQ ..."
    echo "RabbitMQ deleting user \"guest\"."
    rabbitmqctl -n "$RABBITMQ_USER@$RABBITMQ_HOST" delete_user guest 2> /dev/null || :
    echo "RabbitMQ adding user \"$RABBITMQ_USERNAME\"."
    rabbitmqctl -n "$RABBITMQ_USER@$RABBITMQ_HOST" add_user "$RABBITMQ_USERNAME" "$ZULIP_SECRETS_rabbitmq_password" 2> /dev/null || :
    echo "RabbitMQ setting user tags for \"$RABBITMQ_USERNAME\"."
    rabbitmqctl -n "$RABBITMQ_USER@$RABBITMQ_HOST" set_user_tags "$RABBITMQ_USERNAME" administrator 2> /dev/null || :
    echo "RabbitMQ setting permissions for user \"$RABBITMQ_USERNAME\"."
    rabbitmqctl -n "$RABBITMQ_USER@$RABBITMQ_HOST" set_permissions -p / "$RABBITMQ_USERNAME" '.*' '.*' '.*' 2> /dev/null || :
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
        echo "First Start Init not needed."
        return 0
    fi
    set +e
    if ! su zulip -c "/home/zulip/deployments/current/manage.py migrate --noinput"; then
        local RETURN_CODE=$?
        echo "Zulip first start init failed in \"migrate --noinput\". with exit code $RETURN_CODE"
        exit $RETURN_CODE
    fi
    echo "Creating Zulip cache and third_party_api_results tables ..."
    if ! su zulip -c "/home/zulip/deployments/current/manage.py createcachetable third_party_api_results"; then
        local RETURN_CODE=$?
        echo "Zulip first start init failed in \"createcachetable third_party_api_results\" with exit code $RETURN_CODE."
        exit $RETURN_CODE
    fi
    echo "Initializing Zulip Voyager database ..."
    if ! su zulip -c "/home/zulip/deployments/current/manage.py initialize_voyager_db"; then
        local RETURN_CODE=$?
        echo "Zulip first start init failed in \"initialize_voyager_db\" with exit code $RETURN_CODE."
        exit $RETURN_CODE
    fi
    set -e
    touch "$DATA_DIR/.initiated"
    echo "Zulip first start init sucessful."
}
zulipMigration() {
    echo "Migrating Zulip to new version ..."
    if [ -e "$DATA_DIR/.zulip-$ZULIP_VERSION" ]; then
        echo "No Zulip migration needed. Continuing."
        return 0
    fi
    set +e
    if ! su zulip -c "/home/zulip/deployments/current/manage.py migrate"; then
        local RETURN_CODE=$?
        echo "Zulip migration failed."
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
    if [ "$(ls -A "$DATA_DIR/post-setup.d/")" ]; then
        echo "No post setup scripts found in \"$DATA_DIR/post-setup.d/\"."
        return 0
    fi
    set +e
    for FILE in $DATA_DIR/post-setup.d/*; do
        if [ -x "$FILE" ]; then
            echo "Executing \"$FILE\" ..."
            bash -c "$FILE"
            echo "Executed \"$FILE\". Return code $?."
        else
            echo "Permissions denied for \"$FILE\". Please check the permissions."
            echo "Post setup scripts execution failed. Exiting."
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
    prepareDirectories
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
        echo "No command given for manage.py. Defaulting to \"shell\""
        COMMAND="shell"
    fi
    echo "Running manage.py ..."
    set +e
    su zulip -c "/home/zulip/deployments/current/manage.py $COMMAND $*"
    exit $?
}
appBackup() {
    echo "Starting backup process ..."
    if [ -d "/tmp/backup-$(date "%D-%H-%M-%S")" ]; then
        echo "Temporary backup folder for \"$(date "%D-%H-%M-%S")\" already exists. Aborting."
        echo "Backup process failed."
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
        echo "Restore process failed."
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
    local TIMEOUT=10
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
    echo "Restore process succeeded."
    exit 0
}
appHelp() {
    echo "Available commands:"
    echo "> app:help     - Show this help menu and exit"
    echo "> app:version  - Container Zulip server version"
    echo "> app:managepy - Run Zulip's manage.py script"
    echo "> app:manage   - Create, Restore and manage backups of Zulip instances"
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
        exec appManagePy "$@"
    ;;
    app:backup)
        appBackup
    ;;
    app:restore)
        appRestore
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
