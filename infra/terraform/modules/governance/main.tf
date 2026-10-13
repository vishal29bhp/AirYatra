# Guardrails: India-only regions, a monthly budget alarm and (optionally) Defender for Cloud plans.

variable "name_prefix" {
  type = string
}
variable "resource_group_id" {
  type = string
}
variable "allowed_locations" {
  type = list(string)
}
variable "monthly_budget_amount" {
  description = "Monthly budget in the billing currency of the subscription."
  type        = number
}
variable "budget_start_date" {
  description = "First day of a month, RFC3339, e.g. 2026-11-01T00:00:00Z."
  type        = string
}
variable "alert_email" {
  type = string
}
variable "enable_defender_plans" {
  description = "Subscription-wide Defender plans. Enable in exactly one environment per subscription."
  type        = bool
  default     = false
}

resource "azurerm_resource_group_policy_assignment" "allowed_locations" {
  name                 = "allowed-locations-india"
  resource_group_id    = var.resource_group_id
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/e56962a6-4747-49cd-b67b-bf8b01975c4c"
  description          = "Primary data stays in India (Constraint 3). Front Door is global and exempt by type."
  parameters = jsonencode({
    listOfAllowedLocations = { value = concat(var.allowed_locations, ["global"]) }
  })
}

resource "azurerm_consumption_budget_resource_group" "this" {
  name              = "budget-${var.name_prefix}"
  resource_group_id = var.resource_group_id
  amount            = var.monthly_budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = [var.alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

locals {
  defender_plans = var.enable_defender_plans ? toset([
    "Containers", "KeyVaults", "StorageAccounts", "Api", "CosmosDbs", "Arm",
  ]) : toset([])
}

resource "azurerm_security_center_subscription_pricing" "this" {
  for_each      = local.defender_plans
  tier          = "Standard"
  resource_type = each.value
}
