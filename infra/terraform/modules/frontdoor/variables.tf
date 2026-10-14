variable "enabled" {
  description = "Create Front Door and its WAF association. False serves the site straight from the static website."
  type        = bool
  default     = true
}
variable "name_prefix" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "location" {
  description = "Region of the static web storage account."
  type        = string
}
variable "sku_name" {
  description = "Premium_AzureFrontDoor (managed WAF rules, bot protection, Private Link to the API) or Standard_AzureFrontDoor."
  type        = string
}
variable "waf_mode" {
  description = "Detection while tuning in dev, Prevention in prod."
  type        = string
}
variable "web_storage_account_name" {
  type = string
}
variable "api_fqdn" {
  type = string
}
variable "api_private_link" {
  description = "When set, Front Door reaches the API through Private Link to the Container Apps environment."
  type = object({
    environment_id = string
    location       = string
  })
  default = null
}
variable "custom_domains" {
  description = "Optional custom host names, e.g. [\"airyatra.co.in\", \"www.airyatra.co.in\"]. DNS validation is a manual step."
  type        = list(string)
  default     = []
}
variable "login_rate_limit_per_minute" {
  description = "Per-IP requests per minute to auth/OTP endpoints before the WAF blocks."
  type        = number
  default     = 30
}
variable "api_rate_limit_per_minute" {
  description = "Per-IP requests per minute to the whole API before the WAF blocks."
  type        = number
  default     = 1200
}
variable "allowed_country_codes" {
  description = "If non-empty, block requests from other countries (geo filter). Empty = no geo filter."
  type        = list(string)
  default     = []
}
variable "log_analytics_workspace_id" {
  type = string
}
variable "tags" {
  type    = map(string)
  default = {}
}
