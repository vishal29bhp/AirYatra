variable "name_prefix" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "retention_in_days" {
  description = "Log Analytics retention. Audit-relevant logs need at least 90 days."
  type        = number
}
variable "alert_email" {
  description = "Address that receives platform alerts."
  type        = string
}
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_in_days
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = "appi-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  # The app ships telemetry with Entra auth through the OpenTelemetry exporter; no ikey in config.
  local_authentication_enabled = false
  tags                         = var.tags
}

resource "azurerm_monitor_action_group" "this" {
  name                = "ag-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  short_name          = "airyatra"
  tags                = var.tags

  email_receiver {
    name                    = "platform-oncall"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

# ---- Alerts required by the master prompt (Phase 1: error rate, latency p95, webhook and scheduler failures) ----

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "error_rate" {
  name                 = "alert-${var.name_prefix}-api-error-rate"
  location             = var.location
  resource_group_name  = var.resource_group_name
  scopes               = [azurerm_application_insights.this.id]
  description          = "More than 1% of API requests failed in the last 5 minutes."
  severity             = 1
  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      requests
      | summarize total = count(), failed = countif(success == false)
      | extend failure_pct = iff(total == 0, 0.0, 100.0 * failed / total)
    KQL
    time_aggregation_method = "Maximum"
    metric_measure_column   = "failure_pct"
    operator                = "GreaterThan"
    threshold               = 1
  }

  action {
    action_groups = [azurerm_monitor_action_group.this.id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "latency_p95" {
  name                 = "alert-${var.name_prefix}-api-latency-p95"
  location             = var.location
  resource_group_name  = var.resource_group_name
  scopes               = [azurerm_application_insights.this.id]
  description          = "API p95 latency above 1.5 s (Q.3 booking/payment ceiling at 20K users)."
  severity             = 2
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      requests
      | summarize p95_ms = percentile(duration, 95)
    KQL
    time_aggregation_method = "Maximum"
    metric_measure_column   = "p95_ms"
    operator                = "GreaterThan"
    threshold               = 1500
  }

  action {
    action_groups = [azurerm_monitor_action_group.this.id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "payment_webhook_failures" {
  name                 = "alert-${var.name_prefix}-payment-webhook-failures"
  location             = var.location
  resource_group_name  = var.resource_group_name
  scopes               = [azurerm_application_insights.this.id]
  description          = "Payment gateway webhooks (Razorpay, Stripe, Cashfree) returned errors."
  severity             = 1
  evaluation_frequency = "PT5M"
  window_duration      = "PT10M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      requests
      | where url has "/webhook" and (url has "razorpay" or url has "stripe" or url has "cashfree" or url has "payment")
      | where success == false
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.this.id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "scheduler_failures" {
  name                 = "alert-${var.name_prefix}-scheduler-job-failures"
  location             = var.location
  resource_group_name  = var.resource_group_name
  scopes               = [azurerm_application_insights.this.id]
  description          = "A background scheduler job logged an exception."
  severity             = 2
  evaluation_frequency = "PT15M"
  window_duration      = "PT15M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      exceptions
      | where cloud_RoleName == "airyatra-worker"
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.this.id]
  }
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.this.id
}
output "application_insights_id" {
  value = azurerm_application_insights.this.id
}
output "application_insights_connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}
output "action_group_id" {
  value = azurerm_monitor_action_group.this.id
}
