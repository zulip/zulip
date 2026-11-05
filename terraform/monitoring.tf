# ============================================================
# Exporters: traducen el estado de cada componente a métricas
# Prometheus. Corren en el namespace de Zulip porque las
# NetworkPolicy de postgres y redis solo admiten clientes de
# ese namespace.
# ============================================================
module "postgres_exporter" {
  source = "./modules/k8s-service"

  name      = "postgres-exporter"
  namespace = kubernetes_namespace_v1.zulip.metadata[0].name
  image     = var.monitoring_images.postgres_exporter
  port      = 9187

  env = {
    DATA_SOURCE_URI  = "${module.postgres.host}:${module.postgres.port}/zulip?sslmode=disable"
    DATA_SOURCE_USER = "zulip"
  }
  secret_env = {
    DATA_SOURCE_PASS = module.secrets.values["postgres_password"]
  }

  probe = {
    tcp = true
  }

  resources = {
    requests = { cpu = "50m", memory = "64Mi" }
    limits   = { memory = "128Mi" }
  }

  labels = local.labels
}

module "redis_exporter" {
  source = "./modules/k8s-service"

  name      = "redis-exporter"
  namespace = kubernetes_namespace_v1.zulip.metadata[0].name
  image     = var.monitoring_images.redis_exporter
  port      = 9121

  env = {
    REDIS_ADDR = "redis://${module.redis.host}:${module.redis.port}"
  }
  secret_env = {
    REDIS_PASSWORD = module.secrets.values["redis_password"]
  }

  probe = {
    tcp = true
  }

  resources = {
    requests = { cpu = "50m", memory = "32Mi" }
    limits   = { memory = "128Mi" }
  }

  labels = local.labels
}

# ============================================================
# Managed Prometheus + Grafana
# ============================================================
module "monitoring" {
  source = "./modules/monitoring"

  project_id             = var.project_id
  name                   = var.name
  grafana_admin_password = module.secrets.values["grafana_admin_password"]
  labels                 = local.labels

  images = {
    grafana   = var.monitoring_images.grafana
    frontend  = var.monitoring_images.gmp_frontend
    collector = var.monitoring_images.otel_collector
  }

  scrape_targets = {
    postgres-exporter = {
      namespace = kubernetes_namespace_v1.zulip.metadata[0].name
      app       = "postgres-exporter"
      port      = module.postgres_exporter.port
    }
    redis-exporter = {
      namespace = kubernetes_namespace_v1.zulip.metadata[0].name
      app       = "redis-exporter"
      port      = module.redis_exporter.port
    }
    # zulip-metrics-server (docker/entrypoint.sh): métricas de los SLI
    # de envío y entrega de mensajes. Solo se expone dentro del Pod;
    # el Service público sigue publicando únicamente el puerto 443.
    zulip = {
      namespace = kubernetes_namespace_v1.zulip.metadata[0].name
      app       = "zulip"
      port      = 9200
    }
  }

  trace_clients = [{
    namespace = kubernetes_namespace_v1.zulip.metadata[0].name
    app       = "zulip"
  }]

  # El CRD PodMonitoring lo instala GKE al habilitar Managed Prometheus.
  depends_on = [module.gke]
}
