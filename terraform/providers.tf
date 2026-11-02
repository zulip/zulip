# Sin bloque credentials: el proveedor usa Application Default
# Credentials (gcloud auth application-default login en local,
# Workload Identity Federation en GitHub Actions). Así nunca hay
# una llave JSON en el repositorio ni en el estado.
provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_client_config" "current" {}

# Se autentica contra GKE con el token OAuth de corta duración de
# la identidad que ejecuta Terraform; no se genera kubeconfig.
# Usa el endpoint DNS, autorizado por IAM, para que funcione desde
# runners de GitHub sin IP fija. Su certificado lo firma una CA
# pública, así que no se pasa cluster_ca_certificate.
provider "kubernetes" {
  host  = "https://${module.gke.dns_endpoint}"
  token = data.google_client_config.current.access_token
}
