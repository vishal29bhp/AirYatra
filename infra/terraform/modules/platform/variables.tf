# ---------------- Identity of the environment ----------------
variable "environment" {
  description = "dev, staging or prod."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}
variable "location" {
  description = "Primary region (Central India)."
  type        = string
  default     = "centralindia"
}
variable "location_short" {
  type    = string
  default = "cin"
}
variable "dr_location" {
  description = "DR region (South India)."
  type        = string
  default     = "southindia"
}
variable "tags" {
  type    = map(string)
  default = {}
}

# ---------------- Network ----------------
variable "vnet_address_space" {
  type = string
}
variable "deployer_ip_cidrs" {
  description = "Public IPs (CIDR) of whoever runs terraform apply, allowed through the Key Vault firewall."
  type        = list(string)
  default     = []
}

# ---------------- Compute (Container Apps) ----------------
variable "api_image" {
  description = "Full image reference. Leave the placeholder for the first apply, CI/CD sets the real image."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}
variable "worker_image" {
  type    = string
  default = "mcr.microsoft.com/k8se/quickstart:latest"
}
variable "api_cpu" {
  type = number
}
variable "api_memory" {
  type = string
}
variable "api_min_replicas" {
  type = number
}
variable "api_max_replicas" {
  type = number
}
variable "worker_cpu" {
  type = number
}
variable "worker_memory" {
  type = string
}
variable "zone_redundancy_enabled" {
  type = bool
}
variable "registry_sku" {
  type = string
}

# ---------------- Data ----------------
variable "storage_replication_type" {
  type = string
}
variable "redis_sku_name" {
  type = string
}
variable "redis_high_availability" {
  type = bool
}
variable "database_engine" {
  description = "atlas (MongoDB Atlas, needs an Atlas org and API key) or cosmos_vcore (Azure Cosmos DB for MongoDB vCore, needs only the subscription)."
  type        = string
  default     = "atlas"
  validation {
    condition     = contains(["atlas", "cosmos_vcore"], var.database_engine)
    error_message = "database_engine must be atlas or cosmos_vcore."
  }
}
variable "cosmos_compute_tier" {
  type    = string
  default = "M10"
}
variable "cosmos_storage_size_in_gb" {
  type    = number
  default = 32
}
variable "cosmos_high_availability" {
  type    = bool
  default = false
}
variable "atlas_org_id" {
  description = "MongoDB Atlas organisation id (MONGODB_ATLAS_PUBLIC_KEY / PRIVATE_KEY come from the environment). Only used when database_engine is atlas."
  type        = string
  default     = ""
}
variable "atlas_instance_size" {
  type = string
}
variable "atlas_autoscale_max_instance_size" {
  type = string
}
variable "atlas_dr_node_enabled" {
  type = bool
}
variable "atlas_mongo_major_version" {
  type    = string
  default = "7.0"
}
variable "atlas_termination_protection" {
  type = bool
}
variable "atlas_backup_restore_window_days" {
  type = number
}
variable "database_name" {
  description = "Must equal the current DB_NAME so data is untouched."
  type        = string
  default     = "airyatra_db"
}

# ---------------- AI ----------------
variable "openai_location" {
  type    = string
  default = "southindia"
}
variable "openai_deployments" {
  type = map(object({
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
}

# ---------------- Edge ----------------
variable "frontdoor_enabled" {
  description = "False skips Front Door (Azure Free Trial subscriptions cannot create it): no WAF or edge headers."
  type        = bool
  default     = true
}
variable "frontdoor_sku" {
  type = string
}
variable "waf_mode" {
  type = string
}
variable "custom_domains" {
  type    = list(string)
  default = []
}
variable "allowed_country_codes" {
  type    = list(string)
  default = []
}
variable "cors_allowed_origins" {
  description = "Explicit browser origins allowed by the API (replaces the *.emergentagent.com default)."
  type        = list(string)
  default     = []
}

# ---------------- Operations ----------------
variable "log_retention_days" {
  type = number
}
variable "alert_email" {
  type = string
}
variable "monthly_budget_amount" {
  type = number
}
variable "budget_start_date" {
  type = string
}
variable "enable_defender_plans" {
  type    = bool
  default = false
}
variable "github_repository" {
  type    = string
  default = "vishal29bhp/AirYatra"
}
variable "access_token_expire_minutes" {
  description = "Short-lived access tokens (S.2 A07)."
  type        = number
  default     = 15
}
variable "enable_load_testing" {
  description = "Azure Load Testing resource for the Q.3 performance suite."
  type        = bool
  default     = false
}

# Third-party secrets that are created as placeholders and then set by hand (never in tfvars or git).
variable "manual_secret_env_vars" {
  description = "Env var names whose values live only in Key Vault and are set with az keyvault secret set."
  type        = list(string)
  default = [
    "FILE_ENCRYPTION_KEY",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET",
    "RAZORPAYX_KEY_ID",
    "RAZORPAYX_KEY_SECRET",
    "RAZORPAYX_ACCOUNT_NUMBER",
    "STRIPE_API_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "CASHFREE_CLIENT_ID",
    "CASHFREE_CLIENT_SECRET",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "SENDGRID_API_KEY",
    "SMTP_PASSWORD",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "OPENWEATHER_API_KEY",
  ]
}

variable "load_test_location" {
  description = "Region for Azure Load Testing when the primary region does not offer it. Null uses location."
  type        = string
  default     = null
}
variable "web_storage_replication_type" {
  description = "Replication of the static website account. ZRS is not offered in every region (for example South India)."
  type        = string
  default     = "ZRS"
}

variable "compute_platform" {
  description = "container_apps (production design) or app_service (dev on an Azure Free Trial, which allows one Container Apps environment per subscription)."
  type        = string
  default     = "container_apps"
  validation {
    condition     = contains(["container_apps", "app_service"], var.compute_platform)
    error_message = "compute_platform must be container_apps or app_service."
  }
}
variable "app_service_sku" {
  type    = string
  default = "B1"
}
