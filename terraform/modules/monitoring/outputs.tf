output "namespace" {
  description = "Namespace de monitoreo."
  value       = kubernetes_namespace_v1.this.metadata[0].name
}

output "grafana_service" {
  description = "Service interno de Grafana (ClusterIP)."
  value       = kubernetes_service_v1.grafana.metadata[0].name
}

output "otlp_endpoint" {
  description = "Endpoint OTLP/HTTP del OpenTelemetry Collector, para OTEL_EXPORTER_OTLP_ENDPOINT."
  value       = "http://${kubernetes_service_v1.collector.metadata[0].name}.${kubernetes_namespace_v1.this.metadata[0].name}.svc:${local.otlp_http_port}"
}
