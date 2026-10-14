variable "environment_enabled" {
  description = "False creates only the registry (dev on App Service, where the trial allows no second Container Apps environment)."
  type        = bool
  default     = true
}
variable "name_prefix" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "infrastructure_subnet_id" {
  type = string
}
variable "internal_only" {
  description = "Internal load balancer: the API is reachable only from the VNet and Front Door Private Link."
  type        = bool
}
variable "zone_redundancy_enabled" {
  type = bool
}
variable "log_analytics_workspace_id" {
  type = string
}
variable "registry_name" {
  type = string
}
variable "registry_sku" {
  type = string
}
variable "identity_id" {
  description = "User-assigned managed identity shared by the API and the worker."
  type        = string
}
variable "identity_client_id" {
  type = string
}

variable "api_image" {
  type = string
}
variable "worker_image" {
  type = string
}
variable "api_port" {
  type    = number
  default = 8001
}
variable "api_cpu" {
  type = number
}
variable "api_memory" {
  type = string
}
variable "api_min_replicas" {
  description = ">= 2 for HA (Phase 1 default)."
  type        = number
}
variable "api_max_replicas" {
  type = number
}
variable "api_concurrent_requests_per_replica" {
  description = "KEDA HTTP scale rule target."
  type        = number
  default     = 50
}
variable "worker_cpu" {
  type = number
}
variable "worker_memory" {
  type = string
}
variable "worker_command" {
  description = "Command that starts the single scheduler worker (APScheduler moved out of the API)."
  type        = list(string)
  default     = ["python", "worker.py"]
}
variable "health_path" {
  description = "Liveness: the process answers."
  type        = string
  default     = "/health"
}
variable "readiness_path" {
  description = "Readiness: the database answers too, so traffic waits until a new revision can serve it."
  type        = string
  default     = "/health/ready"
}

variable "env_vars" {
  description = "Plain (non-secret) environment variables for both containers."
  type        = map(string)
  default     = {}
}
variable "key_vault_secrets" {
  description = "Map of ENV_VAR_NAME => Key Vault secret versionless id. Resolved by Container Apps with the managed identity."
  type        = map(string)
  default     = {}
}
variable "tags" {
  type    = map(string)
  default = {}
}
