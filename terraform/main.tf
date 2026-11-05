locals {
  labels = merge(var.labels, {
    app         = "zulip"
    environment = var.environment
    managed-by  = "terraform"
  })

  # Sin dominio propio se usa la IP estática del LoadBalancer.
  external_host = var.external_host != "" ? var.external_host : module.network.ingress_ip

  # Solo se revela si hay usuario SMTP, no cuál es; así el resto de
  # las variables de entorno de Zulip sigue visible en el plan.
  email_enabled = nonsensitive(var.zulip_email_host_user != "")
}

resource "google_project_service" "this" {
  for_each = toset([
    "compute.googleapis.com",
    "container.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# ============================================================
# Plataforma: red, clúster GKE y credenciales
# ============================================================
module "network" {
  source = "./modules/network"

  project_id    = var.project_id
  name          = var.name
  region        = var.region
  subnet_cidr   = var.subnet_cidr
  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr

  depends_on = [google_project_service.this]
}

module "gke" {
  source = "./modules/gke"

  project_id          = var.project_id
  name                = var.name
  location            = var.zone
  network_name        = module.network.network_name
  subnet_name         = module.network.subnet_name
  pods_range_name     = module.network.pods_range_name
  services_range_name = module.network.services_range_name
  master_cidr         = var.master_cidr
  authorized_networks = var.authorized_networks
  machine_type        = var.machine_type
  node_count          = var.node_count
  disk_size_gb        = var.disk_size_gb
  deletion_protection = var.deletion_protection
  labels              = local.labels
}

module "secrets" {
  source = "./modules/secrets"

  project_id = var.project_id
  name       = var.name
  labels     = local.labels

  secret_lengths = {
    postgres_password      = 32
    rabbitmq_password      = 32
    redis_password         = 32
    memcached_password     = 32
    zulip_secret_key       = 64
    grafana_admin_password = 32
  }

  depends_on = [google_project_service.this]
}

# ============================================================
# Componentes: cada uno es un contenedor en GKE, traducido de
# su docker-compose.yml en deploy/
# ============================================================
resource "kubernetes_namespace_v1" "zulip" {
  metadata {
    name   = var.namespace
    labels = local.labels
  }

  # Los Pods necesitan nodos; el pool se crea después del clúster.
  depends_on = [module.gke]
}

module "postgres" {
  source = "./modules/k8s-service"

  name      = "postgres"
  namespace = kubernetes_namespace_v1.zulip.metadata[0].name
  image     = var.images.postgres
  port      = 5432

  env = {
    POSTGRES_DB   = "zulip"
    POSTGRES_USER = "zulip"
    # Los discos de GCE traen lost+found en la raíz; PostgreSQL
    # exige un directorio de datos vacío.
    PGDATA = "/var/lib/postgresql/data/pgdata"
  }
  secret_env = {
    POSTGRES_PASSWORD = module.secrets.values["postgres_password"]
  }

  volume = {
    size       = var.storage_sizes.postgres
    mount_path = "/var/lib/postgresql/data"
  }

  probe = {
    exec = ["pg_isready", "-U", "zulip", "-d", "zulip"]
  }

  resources = {
    requests = { cpu = "250m", memory = "512Mi" }
    limits   = { memory = "2Gi" }
  }

  allowed_clients = ["zulip", "postgres-exporter"]
  labels          = local.labels
}

module "redis" {
  source = "./modules/k8s-service"

  name      = "redis"
  namespace = kubernetes_namespace_v1.zulip.metadata[0].name
  image     = var.images.redis
  port      = 6379

  args = ["sh", "-euc", "exec redis-server --requirepass \"$REDIS_PASSWORD\""]

  secret_env = {
    REDIS_PASSWORD = module.secrets.values["redis_password"]
  }

  probe = {
    exec = ["sh", "-c", "REDISCLI_AUTH=\"$REDIS_PASSWORD\" redis-cli ping | grep PONG"]
  }

  resources = {
    requests = { cpu = "100m", memory = "128Mi" }
    limits   = { memory = "512Mi" }
  }

  allowed_clients = ["zulip", "redis-exporter"]
  labels          = local.labels
}

module "memcached" {
  source = "./modules/k8s-service"

  name      = "memcached"
  namespace = kubernetes_namespace_v1.zulip.metadata[0].name
  image     = var.images.memcached
  port      = 11211

  args = ["sh", "-euc", <<-EOT
    echo 'mech_list: plain' > "$SASL_CONF_PATH"
    echo "zulip@$HOSTNAME:$MEMCACHED_PASSWORD" > "$MEMCACHED_SASL_PWDB"
    echo "zulip@localhost:$MEMCACHED_PASSWORD" >> "$MEMCACHED_SASL_PWDB"
    exec memcached -S
  EOT
  ]

  env = {
    SASL_CONF_PATH      = "/home/memcache/memcached.conf"
    MEMCACHED_SASL_PWDB = "/home/memcache/memcached-sasl-db"
  }
  secret_env = {
    MEMCACHED_PASSWORD = module.secrets.values["memcached_password"]
  }

  probe = {
    tcp = true
  }

  resources = {
    requests = { cpu = "100m", memory = "128Mi" }
    limits   = { memory = "512Mi" }
  }

  allowed_clients = ["zulip"]
  labels          = local.labels
}

module "rabbitmq" {
  source = "./modules/k8s-service"

  name      = "rabbitmq"
  namespace = kubernetes_namespace_v1.zulip.metadata[0].name
  image     = var.images.rabbitmq
  port      = 5672

  env = {
    RABBITMQ_DEFAULT_USER = "zulip"
    # RabbitMQ guarda sus datos en un directorio con el nombre del
    # nodo; con un nombre fijo los datos sobreviven a que el Pod
    # cambie de hostname al recrearse.
    RABBITMQ_NODENAME = "rabbit@localhost"
  }
  secret_env = {
    RABBITMQ_DEFAULT_PASS = module.secrets.values["rabbitmq_password"]
  }

  volume = {
    size       = var.storage_sizes.rabbitmq
    mount_path = "/var/lib/rabbitmq"
  }

  probe = {
    exec = ["rabbitmq-diagnostics", "-q", "ping"]
  }

  resources = {
    requests = { cpu = "250m", memory = "512Mi" }
    limits   = { memory = "1Gi" }
  }

  allowed_clients = ["zulip"]
  labels          = local.labels
}

module "zulip" {
  source = "./modules/k8s-service"

  name      = "zulip"
  namespace = kubernetes_namespace_v1.zulip.metadata[0].name
  image     = var.images.zulip
  port      = 443

  # Reemplaza al servicio zulip-init de deploy/app.
  init_args = ["app:init"]

  env = merge({
    SETTING_REMOTE_POSTGRES_HOST = module.postgres.host
    SETTING_MEMCACHED_LOCATION   = "${module.memcached.host}:${module.memcached.port}"
    SETTING_RABBITMQ_HOST        = module.rabbitmq.host
    SETTING_REDIS_HOST           = module.redis.host

    SETTING_EXTERNAL_HOST = local.external_host

    CERTIFICATES = "self-signed"

    CONFIG_application_server__queue_workers_multiprocess = "false"

    # Trazas (zerver/lib/tracing.py); sin el endpoint, Zulip no
    # instrumenta nada.
    OTEL_EXPORTER_OTLP_ENDPOINT = module.monitoring.otlp_endpoint
    OTEL_TRACES_SAMPLER_ARG     = tostring(var.trace_sample_ratio)
    }, var.external_host != "" ? {} : {
    # Zulip arma correos de bots y usuarios ficticios con el dominio
    # de EXTERNAL_HOST; una IP no es un dominio válido y la creación
    # de usuarios falla.
    SETTING_FAKE_EMAIL_DOMAIN = "fake-domain.example.com"
    }, local.email_enabled ? {
    SETTING_EMAIL_HOST    = var.zulip_email_host
    SETTING_EMAIL_PORT    = tostring(var.zulip_email_port)
    SETTING_EMAIL_USE_TLS = "True"
    # Gmail reescribe el remitente a la cuenta autenticada; las
    # direcciones noreply con token no sobrevivirían.
    SETTING_ADD_TOKENS_TO_NOREPLY_ADDRESS = "False"
  } : {})
  secret_env = merge({
    SECRETS_postgres_password  = module.secrets.values["postgres_password"]
    SECRETS_rabbitmq_password  = module.secrets.values["rabbitmq_password"]
    SECRETS_redis_password     = module.secrets.values["redis_password"]
    SECRETS_memcached_password = module.secrets.values["memcached_password"]
    SECRETS_secret_key         = module.secrets.values["zulip_secret_key"]
    SECRETS_email_password     = var.zulip_email_password

    # Va en el Secret y no en env para que el correo no aparezca en
    # el plan; el contenedor lo recibe igual como variable de entorno.
    SETTING_ZULIP_ADMINISTRATOR = var.zulip_administrator
    }, local.email_enabled ? {
    SETTING_EMAIL_HOST_USER       = var.zulip_email_host_user
    SETTING_NOREPLY_EMAIL_ADDRESS = var.zulip_email_host_user
  } : {})

  volume = {
    size       = var.storage_sizes.zulip
    mount_path = "/data"
  }

  # Mismo healthcheck que deploy/app. Un httpGet del kubelet no
  # sirve: usa la IP del Pod como Host y Django lo rechaza por no
  # estar en ALLOWED_HOSTS.
  probe = {
    exec                      = ["curl", "-isfL", "--insecure", "https://localhost/health"]
    startup_failure_threshold = 60
  }

  resources = {
    requests = { cpu = "1", memory = "3Gi" }
    limits   = { memory = "6Gi" }
  }

  service_type     = "LoadBalancer"
  load_balancer_ip = module.network.ingress_ip
  labels           = local.labels

  # Equivale a depends_on: condition: service_healthy del compose:
  # cada Deployment de respaldo espera su rollout (readiness probe).
  depends_on = [module.postgres, module.redis, module.memcached, module.rabbitmq]
}
