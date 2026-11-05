# ============================================================
# Trazas. Zulip envía spans por OTLP/HTTP a un OpenTelemetry
# Collector, que los exporta a Cloud Trace. El Collector es el
# único con credenciales (Workload Identity), así que la imagen de
# Zulip no necesita clientes ni cuentas de Google.
# ============================================================
locals {
  collector_name = "otel-collector"
  otlp_http_port = 4318
  health_port    = 13133
}

resource "google_service_account" "collector" {
  project      = var.project_id
  account_id   = "${var.name}-trace-writer"
  display_name = "OpenTelemetry Collector ${var.name}"
}

# Solo escribe trazas; no puede leerlas ni tocar métricas o logs.
resource "google_project_iam_member" "collector" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.collector.email}"
}

resource "kubernetes_service_account_v1" "collector" {
  metadata {
    name      = local.collector_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.collector.email
    }
  }
}

resource "google_service_account_iam_member" "collector_workload_identity" {
  service_account_id = google_service_account.collector.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${kubernetes_namespace_v1.this.metadata[0].name}/${kubernetes_service_account_v1.collector.metadata[0].name}]"
}

resource "kubernetes_config_map_v1" "collector" {
  metadata {
    name      = local.collector_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  data = {
    "config.yaml" = yamlencode({
      receivers = {
        otlp = {
          protocols = {
            http = { endpoint = "0.0.0.0:${local.otlp_http_port}" }
          }
        }
      }
      processors = {
        # Descarta spans antes de que el contenedor llegue a su límite
        # de memoria, en vez de que el kernel lo mate.
        memory_limiter = {
          check_interval         = "1s"
          limit_percentage       = 80
          spike_limit_percentage = 20
        }
        batch = {}
      }
      exporters = {
        googlecloud = { project = var.project_id }
      }
      extensions = {
        health_check = { endpoint = "0.0.0.0:${local.health_port}" }
      }
      service = {
        extensions = ["health_check"]
        pipelines = {
          traces = {
            receivers  = ["otlp"]
            processors = ["memory_limiter", "batch"]
            exporters  = ["googlecloud"]
          }
        }
      }
    })
  }
}

resource "kubernetes_deployment_v1" "collector" {
  metadata {
    name      = local.collector_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = merge(local.labels, { app = local.collector_name })
  }

  spec {
    replicas = 1

    selector {
      match_labels = { app = local.collector_name }
    }

    template {
      metadata {
        labels = merge(local.labels, { app = local.collector_name })
        annotations = {
          "checksum/config" = sha256(kubernetes_config_map_v1.collector.data["config.yaml"])
        }
      }

      spec {
        service_account_name = kubernetes_service_account_v1.collector.metadata[0].name

        container {
          name  = local.collector_name
          image = var.images.collector
          args  = ["--config=/etc/otelcol-contrib/config.yaml"]

          port {
            container_port = local.otlp_http_port
          }

          resources {
            requests = { cpu = "50m", memory = "128Mi" }
            limits   = { memory = "256Mi" }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "config"
            mount_path = "/etc/otelcol-contrib"
            read_only  = true
          }

          readiness_probe {
            http_get {
              path = "/"
              port = local.health_port
            }
            period_seconds = 10
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map_v1.collector.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [google_service_account_iam_member.collector_workload_identity]
}

resource "kubernetes_service_v1" "collector" {
  metadata {
    name      = local.collector_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  spec {
    type     = "ClusterIP"
    selector = { app = local.collector_name }

    port {
      port        = local.otlp_http_port
      target_port = local.otlp_http_port
    }
  }
}

# Solo los Pods listados en trace_clients pueden enviar spans: el
# Collector escribe en Cloud Trace con su propia identidad.
resource "kubernetes_network_policy_v1" "collector" {
  metadata {
    name      = "${local.collector_name}-ingress"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    pod_selector {
      match_labels = { app = local.collector_name }
    }

    policy_types = ["Ingress"]

    ingress {
      ports {
        port     = local.otlp_http_port
        protocol = "TCP"
      }

      dynamic "from" {
        for_each = var.trace_clients
        content {
          namespace_selector {
            match_labels = { "kubernetes.io/metadata.name" = from.value.namespace }
          }
          pod_selector {
            match_labels = { app = from.value.app }
          }
        }
      }
    }
  }
}
