variable "project_id" {
  description = "ID del proyecto de GCP."
  type        = string
}

variable "name" {
  description = "Nombre del clúster; también se usa como prefijo del pool y la cuenta de servicio."
  type        = string
}

variable "location" {
  description = "Zona (clúster zonal) o región (clúster regional) del clúster."
  type        = string
}

variable "network_name" {
  description = "Nombre de la VPC donde se crea el clúster."
  type        = string
}

variable "subnet_name" {
  description = "Nombre de la subred de los nodos."
  type        = string
}

variable "pods_range_name" {
  description = "Nombre del rango secundario de la subred para Pods."
  type        = string
}

variable "services_range_name" {
  description = "Nombre del rango secundario de la subred para Services."
  type        = string
}

variable "master_cidr" {
  description = "Rango /28 para el plano de control privado."
  type        = string
}

variable "authorized_networks" {
  description = "Redes autorizadas para acceder a la API de Kubernetes."
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  sensitive = true
}

variable "machine_type" {
  description = "Tipo de máquina de los nodos."
  type        = string
}

variable "node_count" {
  description = "Número de nodos del pool."
  type        = number
}

variable "disk_size_gb" {
  description = "Tamaño del disco de arranque de cada nodo (GB)."
  type        = number
}

variable "deletion_protection" {
  description = "Impide que terraform destroy elimine el clúster."
  type        = bool
}

variable "labels" {
  description = "Etiquetas aplicadas al clúster y a los nodos."
  type        = map(string)
}
