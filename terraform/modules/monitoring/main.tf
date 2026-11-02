# ============================================================
# Monitoreo con Google Cloud Managed Service for Prometheus.
# GKE corre los collectors (gmp-system); este módulo agrega:
#   - PodMonitoring: qué Pods scrapear.
#   - Frontend de consultas: expone la API de Prometheus sobre
#     Cloud Monitoring, autenticado con Workload Identity.
#   - Grafana, con el frontend como data source.
# ============================================================
locals {
  labels = merge(var.labels, { component = "monitoring" })

  frontend_name = "gmp-frontend"
  frontend_port = 9090
  grafana_port  = 3000
}

resource "kubernetes_namespace_v1" "this" {
  metadata {
    name   = var.namespace
    labels = local.labels
  }
}

# ------------------------------------------------------------
# Qué scrapear. Un PodMonitoring por componente; el collector
# del nodo scrapea cada Pod que coincide con el selector.
# ------------------------------------------------------------
resource "kubernetes_manifest" "pod_monitoring" {
  for_each = var.scrape_targets

  manifest = {
    apiVersion = "monitoring.googleapis.com/v1"
    kind       = "PodMonitoring"
    metadata = {
      name      = each.key
      namespace = each.value.namespace
      labels    = local.labels
    }
    spec = {
      selector = {
        matchLabels = { app = each.value.app }
      }
      endpoints = [{
        port     = each.value.port
        path     = each.value.path
        interval = var.scrape_interval
      }]
    }
  }
}

# ------------------------------------------------------------
# Identidad del frontend: solo lectura de Cloud Monitoring.
# ------------------------------------------------------------
resource "google_service_account" "frontend" {
  project      = var.project_id
  account_id   = "${var.name}-gmp-reader"
  display_name = "Frontend de Managed Prometheus ${var.name}"
}

resource "google_project_iam_member" "frontend" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.frontend.email}"
}

resource "kubernetes_service_account_v1" "frontend" {
  metadata {
    name      = local.frontend_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.frontend.email
    }
  }
}

resource "google_service_account_iam_member" "frontend_workload_identity" {
  service_account_id = google_service_account.frontend.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${kubernetes_namespace_v1.this.metadata[0].name}/${kubernetes_service_account_v1.frontend.metadata[0].name}]"
}

resource "kubernetes_deployment_v1" "frontend" {
  metadata {
    name      = local.frontend_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = merge(local.labels, { app = local.frontend_name })
  }

  spec {
    replicas = 1

    selector {
      match_labels = { app = local.frontend_name }
    }

    template {
      metadata {
        labels = merge(local.labels, { app = local.frontend_name })
      }

      spec {
        service_account_name = kubernetes_service_account_v1.frontend.metadata[0].name

        container {
          name  = local.frontend_name
          image = var.images.frontend
          args = [
            "--web.listen-address=:${local.frontend_port}",
            "--query.project-id=${var.project_id}",
          ]

          port {
            container_port = local.frontend_port
          }

          resources {
            requests = { cpu = "50m", memory = "64Mi" }
            limits   = { memory = "256Mi" }
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            capabilities {
              drop = ["ALL"]
            }
          }

          readiness_probe {
            tcp_socket {
              port = local.frontend_port
            }
            period_seconds = 10
          }
        }
      }
    }
  }

  depends_on = [google_service_account_iam_member.frontend_workload_identity]
}

resource "kubernetes_service_v1" "frontend" {
  metadata {
    name      = local.frontend_name
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  spec {
    type     = "ClusterIP"
    selector = { app = local.frontend_name }

    port {
      port        = local.frontend_port
      target_port = local.frontend_port
    }
  }
}

# Solo Grafana consulta el frontend: cualquier Pod que lo alcance
# lee todas las métricas del proyecto.
resource "kubernetes_network_policy_v1" "frontend" {
  metadata {
    name      = "${local.frontend_name}-ingress"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
  }

  spec {
    pod_selector {
      match_labels = { app = local.frontend_name }
    }

    policy_types = ["Ingress"]

    ingress {
      ports {
        port     = local.frontend_port
        protocol = "TCP"
      }

      from {
        pod_selector {
          match_labels = { app = "grafana" }
        }
      }
    }
  }
}

# ------------------------------------------------------------
# Grafana. Sin Service público: se accede con kubectl
# port-forward. Sin disco: datasource y dashboards se
# aprovisionan desde ConfigMaps, así que el Pod es desechable.
# ------------------------------------------------------------
resource "kubernetes_secret_v1" "grafana" {
  metadata {
    name      = "grafana-env"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  data = {
    GF_SECURITY_ADMIN_PASSWORD = var.grafana_admin_password
  }
}

resource "kubernetes_config_map_v1" "grafana_datasources" {
  metadata {
    name      = "grafana-datasources"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  data = {
    "managed-prometheus.yaml" = yamlencode({
      apiVersion = 1
      datasources = [{
        name      = "Managed Prometheus"
        uid       = "managed-prometheus"
        type      = "prometheus"
        access    = "proxy"
        url       = "http://${local.frontend_name}.${kubernetes_namespace_v1.this.metadata[0].name}.svc:${local.frontend_port}"
        isDefault = true
        editable  = false
      }]
    })
  }
}

# Dashboards como código: el Pod de Grafana no tiene disco, así que
# lo creado en la interfaz se pierde al reiniciar. Para cambiar un
# dashboard, se edita su JSON en dashboards/.
resource "kubernetes_config_map_v1" "grafana_dashboard_provider" {
  metadata {
    name      = "grafana-dashboard-provider"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  data = {
    "dashboards.yaml" = yamlencode({
      apiVersion = 1
      providers = [{
        name                  = "zulip"
        folder                = "Zulip"
        type                  = "file"
        disableDeletion       = true
        allowUiUpdates        = false
        updateIntervalSeconds = 60
        options               = { path = "/var/lib/grafana/dashboards" }
      }]
    })
  }
}

resource "kubernetes_config_map_v1" "grafana_dashboards" {
  metadata {
    name      = "grafana-dashboards"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  data = {
    "zulip-slo.json" = file("${path.module}/../../../observability/dashboards/zulip-slo.json")
  }
}

# Reglas de alerta (Burn Rate Alerting) y enrutamiento de
# notificaciones, como código en /observability/alerting. Mismo
# patrón que el dashboard: el Pod no tiene disco, así que Terraform
# solo inyecta los YAML sin interpretarlos; Grafana los lee al
# arrancar (provisioning nativo). Un solo ConfigMap: Grafana espera
# todos los archivos de alerting juntos en un mismo directorio plano.
resource "kubernetes_config_map_v1" "grafana_alerting" {
  metadata {
    name      = "grafana-alerting"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  data = {
    "availability-burn-rate.yaml" = file("${path.module}/../../../observability/alerting/rules/availability-burn-rate.yaml")
    "latency-burn-rate.yaml"      = file("${path.module}/../../../observability/alerting/rules/latency-burn-rate.yaml")
    "contactpoints.yaml"          = file("${path.module}/../../../observability/alerting/contactpoints.yaml")
    "notification-policies.yaml"  = file("${path.module}/../../../observability/alerting/notification-policies.yaml")
  }
}

resource "kubernetes_deployment_v1" "grafana" {
  metadata {
    name      = "grafana"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = merge(local.labels, { app = "grafana" })
  }

  spec {
    replicas = 1

    selector {
      match_labels = { app = "grafana" }
    }

    template {
      metadata {
        labels = merge(local.labels, { app = "grafana" })
        annotations = {
          # Fuerza un rollout cuando cambian el datasource, los
          # dashboards o la contraseña.
          "checksum/config" = sha256(jsonencode([
            kubernetes_config_map_v1.grafana_datasources.data,
            kubernetes_config_map_v1.grafana_dashboard_provider.data,
            kubernetes_config_map_v1.grafana_dashboards.data,
            kubernetes_config_map_v1.grafana_alerting.data,
          ]))
          "checksum/secret" = sha256(var.grafana_admin_password)
        }
      }

      spec {
        automount_service_account_token = false

        container {
          name  = "grafana"
          image = var.images.grafana

          port {
            container_port = local.grafana_port
          }

          env {
            name  = "GF_SECURITY_ADMIN_USER"
            value = "admin"
          }
          env {
            name  = "GF_USERS_ALLOW_SIGN_UP"
            value = "false"
          }
          env {
            name  = "GF_AUTH_ANONYMOUS_ENABLED"
            value = "false"
          }
          env {
            name  = "GF_ANALYTICS_REPORTING_ENABLED"
            value = "false"
          }

          env_from {
            secret_ref {
              name = kubernetes_secret_v1.grafana.metadata[0].name
            }
          }

          # Grafana 13 corre cada plugin de datasource incluido como un
          # proceso aparte; con 512Mi el kernel lo mataba (OOMKilled) al
          # cargar el dashboard de SLO.
          resources {
            requests = { cpu = "100m", memory = "512Mi" }
            limits   = { memory = "1Gi" }
          }

          security_context {
            allow_privilege_escalation = false
            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "datasources"
            mount_path = "/etc/grafana/provisioning/datasources"
            read_only  = true
          }

          volume_mount {
            name       = "dashboard-provider"
            mount_path = "/etc/grafana/provisioning/dashboards"
            read_only  = true
          }

          volume_mount {
            name       = "dashboards"
            mount_path = "/var/lib/grafana/dashboards"
            read_only  = true
          }

          volume_mount {
            name       = "alerting"
            mount_path = "/etc/grafana/provisioning/alerting"
            read_only  = true
          }

          readiness_probe {
            http_get {
              path = "/api/health"
              port = local.grafana_port
            }
            period_seconds = 10
          }
        }

        volume {
          name = "datasources"
          config_map {
            name = kubernetes_config_map_v1.grafana_datasources.metadata[0].name
          }
        }

        volume {
          name = "dashboard-provider"
          config_map {
            name = kubernetes_config_map_v1.grafana_dashboard_provider.metadata[0].name
          }
        }

        volume {
          name = "dashboards"
          config_map {
            name = kubernetes_config_map_v1.grafana_dashboards.metadata[0].name
          }
        }

        volume {
          name = "alerting"
          config_map {
            name = kubernetes_config_map_v1.grafana_alerting.metadata[0].name
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "grafana" {
  metadata {
    name      = "grafana"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  spec {
    type     = "ClusterIP"
    selector = { app = "grafana" }

    port {
      port        = local.grafana_port
      target_port = local.grafana_port
    }
  }
}
