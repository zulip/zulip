output "namespace" {
  description = "Namespace de monitoreo."
  value       = kubernetes_namespace_v1.this.metadata[0].name
}

output "grafana_service" {
  description = "Service interno de Grafana (ClusterIP)."
  value       = kubernetes_service_v1.grafana.metadata[0].name
}
