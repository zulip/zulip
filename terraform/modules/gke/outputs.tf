output "cluster_name" {
  description = "Nombre del clúster GKE."
  value       = google_container_cluster.this.name
}

output "endpoint" {
  description = "Endpoint de la API de Kubernetes."
  value       = google_container_cluster.this.endpoint
}

output "ca_certificate" {
  description = "Certificado de la CA del clúster (base64)."
  value       = google_container_cluster.this.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "node_service_account" {
  description = "Correo de la cuenta de servicio de los nodos."
  value       = google_service_account.nodes.email
}

output "dns_endpoint" {
  description = "Endpoint DNS de la API de Kubernetes (autorizado por IAM)."
  value       = google_container_cluster.this.control_plane_endpoints_config[0].dns_endpoint_config[0].endpoint
}
