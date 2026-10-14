variable "subscription_id" {
  description = "Azure subscription that hosts this environment."
  type        = string
}
variable "database_engine" {
  description = "cosmos_vcore (Terraform creates everything) or atlas (needs an Atlas org and keys)."
  type        = string
  default     = "cosmos_vcore"
}
variable "atlas_org_id" {
  description = "Only needed if database_engine is switched to atlas."
  type        = string
  default     = ""
}
variable "alert_email" {
  type = string
}
variable "deployer_ip_cidrs" {
  description = "Your public IP as a /32 so terraform can write Key Vault secrets."
  type        = list(string)
  default     = []
}
variable "custom_domains" {
  type    = list(string)
  default = []
}
variable "api_image" {
  type    = string
  default = "mcr.microsoft.com/k8se/quickstart:latest"
}
variable "worker_image" {
  type    = string
  default = "mcr.microsoft.com/k8se/quickstart:latest"
}
variable "budget_start_date" {
  description = "First day of the month the budget starts, e.g. 2026-11-01T00:00:00Z."
  type        = string
}
