variable "project_id" {
  description = "Proyecto de GCP donde Managed Prometheus guarda las métricas."
  type        = string
}

variable "name" {
  description = "Prefijo de los recursos de GCP (cuenta de servicio)."
  type        = string
}

variable "namespace" {
  description = "Namespace de Kubernetes donde corren Grafana y el frontend de consultas."
  type        = string
  default     = "monitoring"
}

variable "images" {
  description = "Imágenes de Grafana y del frontend de Managed Prometheus."
  type = object({
    grafana  = string
    frontend = string
  })
}

variable "grafana_admin_password" {
  description = "Contraseña del usuario admin de Grafana."
  type        = string
  sensitive   = true
}

variable "scrape_targets" {
  description = "Pods que Managed Prometheus debe scrapear: namespace, label app y puerto de /metrics."
  type = map(object({
    namespace = string
    app       = string
    port      = number
    path      = optional(string, "/metrics")
  }))
  default = {}
}

variable "scrape_interval" {
  description = "Intervalo de scrape. El costo de Managed Prometheus es proporcional a las muestras ingeridas."
  type        = string
  default     = "60s"
}

variable "labels" {
  description = "Etiquetas comunes de Kubernetes."
  type        = map(string)
  default     = {}
}
