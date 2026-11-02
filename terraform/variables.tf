# ============================================================
# Proyecto y ubicación
# ============================================================
variable "project_id" {
  description = "ID del proyecto de GCP donde se despliega Zulip."
  type        = string
}

variable "region" {
  description = "Región de GCP para la red, el NAT y la IP pública."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zona del clúster GKE (clúster zonal para reducir costos); debe pertenecer a region."
  type        = string
  default     = "us-central1-a"
}

variable "name" {
  description = "Prefijo de los recursos de GCP (VPC, clúster, secretos)."
  type        = string
  default     = "zulip"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,18}$", var.name))
    error_message = "name debe tener entre 2 y 19 caracteres: minúsculas, dígitos y guiones, empezando por letra."
  }
}

variable "environment" {
  description = "Nombre del entorno (dev, staging, prod); se agrega como etiqueta."
  type        = string
  default     = "dev"
}

variable "labels" {
  description = "Etiquetas adicionales para todos los recursos."
  type        = map(string)
  default     = {}
}

# ============================================================
# Red
# ============================================================
variable "subnet_cidr" {
  description = "Rango primario de la subred (nodos)."
  type        = string
  default     = "10.10.0.0/20"
}

variable "pods_cidr" {
  description = "Rango secundario para Pods."
  type        = string
  default     = "10.20.0.0/16"
}

variable "services_cidr" {
  description = "Rango secundario para Services."
  type        = string
  default     = "10.30.0.0/20"
}

variable "master_cidr" {
  description = "Rango /28 del plano de control privado de GKE."
  type        = string
  default     = "172.16.0.0/28"
}

variable "authorized_networks" {
  description = "CIDRs que pueden acceder a la API de Kubernetes (p. ej. la IP pública de quien ejecuta Terraform)."
  type = list(object({
    cidr_block   = string
    display_name = string
  }))

  validation {
    condition     = alltrue([for network in var.authorized_networks : network.cidr_block != "0.0.0.0/0"])
    error_message = "No se permite abrir la API de Kubernetes a todo Internet (0.0.0.0/0)."
  }
}

# ============================================================
# Clúster GKE
# ============================================================
variable "machine_type" {
  description = "Tipo de máquina de los nodos. Zulip necesita al menos 4 GB de RAM."
  type        = string
  default     = "e2-standard-4"
}

variable "node_count" {
  description = "Número de nodos del pool."
  type        = number
  default     = 2
}

variable "disk_size_gb" {
  description = "Disco de arranque de cada nodo (GB)."
  type        = number
  default     = 50
}

variable "deletion_protection" {
  description = "Protege el clúster contra terraform destroy. Desactivar solo en entornos efímeros."
  type        = bool
  default     = true
}

# ============================================================
# Aplicación
# ============================================================
variable "namespace" {
  description = "Namespace de Kubernetes para todos los componentes."
  type        = string
  default     = "zulip"
}

variable "images" {
  description = "Imagen de cada componente, fijada a una versión exacta. zulip usa un tag sha-… publicado por docker-image.yml; zulip-postgresql solo publica el tag 14, así que se fija por digest."
  type = object({
    zulip     = string
    postgres  = string
    redis     = string
    memcached = string
    rabbitmq  = string
  })
  default = {
    zulip     = "ghcr.io/facaslo/zulip-server-unal:sha-6709225"
    postgres  = "zulip/zulip-postgresql:14@sha256:e71ba8616fa42cdc1b248f51263d9290c29681cb8c1992eb9b498af0bb656b29"
    redis     = "redis:8.10.3-alpine"
    memcached = "memcached:1.6.45-alpine"
    rabbitmq  = "rabbitmq:4.2.9"
  }
}

variable "storage_sizes" {
  description = "Tamaño de los volúmenes persistentes."
  type = object({
    postgres = string
    rabbitmq = string
    zulip    = string
  })
  default = {
    postgres = "20Gi"
    rabbitmq = "5Gi"
    zulip    = "10Gi"
  }
}

variable "external_host" {
  description = "Dominio público de Zulip. Vacío = usar la IP estática del LoadBalancer."
  type        = string
  default     = ""
}

variable "zulip_administrator" {
  description = "Correo del administrador de Zulip."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.zulip_administrator))
    error_message = "zulip_administrator debe ser un correo válido."
  }
}

variable "zulip_email_password" {
  description = "Contraseña SMTP de Zulip. Pasarla con TF_VAR_zulip_email_password, nunca en un .tfvars versionado."
  type        = string
  default     = ""
  sensitive   = true
}

variable "monitoring_images" {
  description = "Imágenes del stack de monitoreo (exporters, Grafana y frontend de Managed Prometheus)."
  type = object({
    postgres_exporter = string
    redis_exporter    = string
    grafana           = string
    gmp_frontend      = string
  })
  default = {
    postgres_exporter = "quay.io/prometheuscommunity/postgres-exporter:v0.20.1"
    redis_exporter    = "oliver006/redis_exporter:v1.94.0"
    grafana           = "grafana/grafana:13.2.5"
    gmp_frontend      = "gke.gcr.io/prometheus-engine/frontend:v0.19.4-gke.0"
  }
}
