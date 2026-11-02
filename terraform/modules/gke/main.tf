# ============================================================
# Cuenta de servicio de los nodos.
# Se evita la cuenta por defecto de Compute Engine (rol Editor)
# y se otorgan solo los permisos mínimos para logs y métricas.
# ============================================================
resource "google_service_account" "nodes" {
  project      = var.project_id
  account_id   = "${var.name}-nodes"
  display_name = "Nodos GKE ${var.name}"
}

resource "google_project_iam_member" "nodes" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

# ============================================================
# Clúster GKE (Servicio de Kubernetes Gestionado)
# ============================================================
resource "google_container_cluster" "this" {
  project  = var.project_id
  name     = var.name
  location = var.location

  network    = var.network_name
  subnetwork = var.subnet_name

  # El pool por defecto no se puede personalizar; se elimina y se
  # reemplaza por google_container_node_pool.primary.
  remove_default_node_pool = true
  initial_node_count       = 1

  deletion_protection = var.deletion_protection
  resource_labels     = var.labels

  release_channel {
    channel = "REGULAR"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_cidr
  }

  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.authorized_networks
      content {
        cidr_block   = cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  # Endpoint DNS de la API: se autoriza por IAM
  # (container.clusters.connect) en lugar de por IP, así GitHub
  # Actions puede aplicar Terraform sin IPs fijas. Los
  # authorized_networks siguen limitando el endpoint por IP.
  control_plane_endpoints_config {
    dns_endpoint_config {
      allow_external_traffic = true
    }
  }

  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }

  network_policy {
    enabled  = true
    provider = "CALICO"
  }

  addons_config {
    network_policy_config {
      disabled = false
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  enable_shielded_nodes = true
  enable_legacy_abac    = false

  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"

  # Managed Service for Prometheus: GKE instala los collectors
  # (gmp-system) y el CRD PodMonitoring; se cobra por muestra.
  monitoring_config {
    managed_prometheus {
      enabled = true
    }
  }
}

resource "google_container_node_pool" "primary" {
  project    = var.project_id
  name       = "${var.name}-pool"
  location   = var.location
  cluster    = google_container_cluster.this.name
  node_count = var.node_count

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = var.machine_type
    disk_size_gb    = var.disk_size_gb
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = var.labels

    metadata = {
      disable-legacy-endpoints = "true"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}
