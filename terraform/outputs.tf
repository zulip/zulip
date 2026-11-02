output "zulip_url" {
  description = "URL pública de Zulip."
  value       = "https://${local.external_host}"
}

output "ingress_ip" {
  description = "IP estática del LoadBalancer; apuntar aquí el registro DNS si se usa dominio."
  value       = module.network.ingress_ip
}

output "cluster_name" {
  description = "Nombre del clúster GKE."
  value       = module.gke.cluster_name
}

output "get_credentials_command" {
  description = "Comando para configurar kubectl contra el clúster."
  value       = "gcloud container clusters get-credentials ${module.gke.cluster_name} --zone ${var.zone} --project ${var.project_id}"
}

output "namespace" {
  description = "Namespace donde corren los componentes."
  value       = kubernetes_namespace_v1.zulip.metadata[0].name
}

output "internal_endpoints" {
  description = "Host:puerto interno de cada componente (DNS del Service)."
  value = {
    for component in [module.postgres, module.redis, module.memcached, module.rabbitmq, module.zulip] :
    component.host => "${component.host}:${component.port}"
  }
}

output "secret_manager_ids" {
  description = "Secretos en Secret Manager con las credenciales generadas."
  value       = module.secrets.secret_ids
}

output "grafana_port_forward_command" {
  description = "Abre Grafana en http://localhost:3000 (usuario admin; contraseña en Secret Manager: grafana_admin_password)."
  value       = "kubectl -n ${module.monitoring.namespace} port-forward svc/${module.monitoring.grafana_service} 3000:3000"
}
