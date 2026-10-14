variable "name_prefix" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "sku_name" {
  description = "B1 is the smallest plan with VNet integration, which the app needs to reach the private endpoints."
  type        = string
  default     = "B1"
}
variable "subnet_id" {
  description = "Subnet delegated to Microsoft.Web/serverFarms."
  type        = string
}
variable "identity_id" {
  type = string
}
variable "identity_client_id" {
  type = string
}
variable "registry_login_server" {
  type = string
}
variable "image" {
  description = "Image to start with; CI/CD rolls new ones afterwards."
  type        = string
}
variable "api_port" {
  type    = number
  default = 8001
}
variable "health_path" {
  type    = string
  default = "/health"
}
variable "env_vars" {
  type    = map(string)
  default = {}
}
variable "key_vault_secrets" {
  description = "Environment variable name to versionless Key Vault secret id."
  type        = map(string)
  default     = {}
}
variable "tags" {
  type    = map(string)
  default = {}
}
