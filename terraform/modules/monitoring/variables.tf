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
  description = "Imágenes de Grafana, del frontend de Managed Prometheus y del OpenTelemetry Collector."
  type = object({
    grafana   = string
    frontend  = string
    collector = string
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

variable "trace_clients" {
  description = "Pods que pueden enviar trazas al OpenTelemetry Collector: namespace y label app."
  type = list(object({
    namespace = string
    app       = string
  }))
  default = []
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
