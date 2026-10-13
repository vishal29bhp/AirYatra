locals {
  premium = var.sku_name == "Premium_AzureFrontDoor"
}

# ---------------- Static front end (React build) ----------------
# Only public, non-sensitive build assets live here; Front Door caches them at the edge.
resource "azurerm_storage_account" "web" {
  #checkov:skip=CKV2_AZURE_1:Public static build assets only; no customer data.
  #checkov:skip=CKV2_AZURE_33:Static website origin for Front Door; holds no private data.
  #checkov:skip=CKV_AZURE_59:The static website endpoint must be reachable by Front Door.
  #checkov:skip=CKV_AZURE_33:Queue service is not used.
  #checkov:skip=CKV_AZURE_206:ZRS is enough for rebuildable build output.
  name                            = var.web_storage_account_name
  location                        = var.location
  resource_group_name             = var.resource_group_name
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  tags                            = var.tags

  blob_properties {
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_account_static_website" "web" {
  storage_account_id = azurerm_storage_account.web.id
  index_document     = "index.html"
  error_404_document = "index.html"
}

# ---------------- Front Door profile and endpoint ----------------
resource "azurerm_cdn_frontdoor_profile" "this" {
  name                     = "afd-${var.name_prefix}"
  resource_group_name      = var.resource_group_name
  sku_name                 = var.sku_name
  response_timeout_seconds = 120
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "this" {
  name                     = "fde-${var.name_prefix}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_custom_domain" "this" {
  for_each                 = toset(var.custom_domains)
  name                     = replace(each.value, ".", "-")
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  host_name                = each.value

  tls {
    certificate_type = "ManagedCertificate"
  }
}

# ---------------- Origins ----------------
resource "azurerm_cdn_frontdoor_origin_group" "api" {
  name                     = "og-api"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
  session_affinity_enabled = false

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }

  health_probe {
    protocol            = "Https"
    path                = "/health"
    request_type        = "GET"
    interval_in_seconds = 60
  }
}

resource "azurerm_cdn_frontdoor_origin" "api" {
  name                           = "origin-api"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.api.id
  enabled                        = true
  host_name                      = var.api_fqdn
  origin_host_header             = var.api_fqdn
  certificate_name_check_enabled = true
  https_port                     = 443
  http_port                      = 80
  priority                       = 1
  weight                         = 1000

  dynamic "private_link" {
    for_each = var.api_private_link == null ? [] : [var.api_private_link]
    content {
      target_type            = "managedEnvironments"
      private_link_target_id = private_link.value.environment_id
      location               = private_link.value.location
      request_message        = "AirYatra Front Door to API"
    }
  }
}

resource "azurerm_cdn_frontdoor_origin_group" "web" {
  name                     = "og-web"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }

  health_probe {
    protocol            = "Https"
    path                = "/index.html"
    request_type        = "HEAD"
    interval_in_seconds = 120
  }
}

resource "azurerm_cdn_frontdoor_origin" "web" {
  name                           = "origin-web"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.web.id
  enabled                        = true
  host_name                      = azurerm_storage_account.web.primary_web_host
  origin_host_header             = azurerm_storage_account.web.primary_web_host
  certificate_name_check_enabled = true
  priority                       = 1
  weight                         = 1000
}

# ---------------- Edge rules: security headers and SPA fallback ----------------
resource "azurerm_cdn_frontdoor_rule_set" "security" {
  name                     = "securityheaders"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
}

resource "azurerm_cdn_frontdoor_rule" "security_headers" {
  name                      = "addsecurityheaders"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.security.id
  order                     = 1
  behavior_on_match         = "Continue"

  actions {
    response_header_action {
      header_action = "Overwrite"
      header_name   = "Strict-Transport-Security"
      value         = "max-age=63072000; includeSubDomains; preload"
    }
    response_header_action {
      header_action = "Overwrite"
      header_name   = "X-Content-Type-Options"
      value         = "nosniff"
    }
    response_header_action {
      header_action = "Overwrite"
      header_name   = "Referrer-Policy"
      value         = "strict-origin-when-cross-origin"
    }
    response_header_action {
      header_action = "Overwrite"
      header_name   = "X-Frame-Options"
      value         = "DENY"
    }
    response_header_action {
      header_action = "Overwrite"
      header_name   = "Permissions-Policy"
      value         = "camera=(), microphone=(self), geolocation=(self), payment=(self)"
    }
  }
}

resource "azurerm_cdn_frontdoor_rule_set" "spa" {
  name                     = "spafallback"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id
}

# Client-side routes (/booking, /admin/...) have no file extension: serve index.html with a 200.
resource "azurerm_cdn_frontdoor_rule" "spa_fallback" {
  name                      = "rewritetoindex"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.spa.id
  order                     = 1
  behavior_on_match         = "Stop"

  conditions {
    url_file_extension_condition {
      operator     = "LessThan"
      match_values = ["1"]
    }
  }

  actions {
    url_rewrite_action {
      source_pattern          = "/"
      destination             = "/index.html"
      preserve_unmatched_path = false
    }
  }
}

# ---------------- Routes ----------------
resource "azurerm_cdn_frontdoor_route" "api" {
  name                            = "route-api"
  cdn_frontdoor_endpoint_id       = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.api.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.api.id]
  cdn_frontdoor_rule_set_ids      = [azurerm_cdn_frontdoor_rule_set.security.id]
  cdn_frontdoor_custom_domain_ids = [for d in azurerm_cdn_frontdoor_custom_domain.this : d.id]
  patterns_to_match               = ["/api/*", "/health"]
  supported_protocols             = ["Http", "Https"]
  https_redirect_enabled          = true
  forwarding_protocol             = "HttpsOnly"
  link_to_default_domain          = true
  # No cache block: API responses are never cached at the edge.
}

resource "azurerm_cdn_frontdoor_route" "web" {
  name                            = "route-web"
  cdn_frontdoor_endpoint_id       = azurerm_cdn_frontdoor_endpoint.this.id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.web.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.web.id]
  cdn_frontdoor_rule_set_ids      = [azurerm_cdn_frontdoor_rule_set.security.id, azurerm_cdn_frontdoor_rule_set.spa.id]
  cdn_frontdoor_custom_domain_ids = [for d in azurerm_cdn_frontdoor_custom_domain.this : d.id]
  patterns_to_match               = ["/*"]
  supported_protocols             = ["Http", "Https"]
  https_redirect_enabled          = true
  forwarding_protocol             = "HttpsOnly"
  link_to_default_domain          = true

  cache {
    query_string_caching_behavior = "IgnoreQueryString"
    compression_enabled           = true
    content_types_to_compress     = ["text/html", "text/css", "application/javascript", "application/json", "image/svg+xml"]
  }
}

# ---------------- WAF ----------------
resource "azurerm_cdn_frontdoor_firewall_policy" "this" {
  name                              = replace("waf${var.name_prefix}", "-", "")
  resource_group_name               = var.resource_group_name
  sku_name                          = var.sku_name
  enabled                           = true
  mode                              = var.waf_mode
  request_body_check_enabled        = true
  custom_block_response_status_code = 403
  tags                              = var.tags

  dynamic "managed_rule" {
    for_each = local.premium ? [1] : []
    content {
      type    = "Microsoft_DefaultRuleSet"
      version = "2.1"
      action  = "Block"
    }
  }

  dynamic "managed_rule" {
    for_each = local.premium ? [1] : []
    content {
      type    = "Microsoft_BotManagerRuleSet"
      version = "1.1"
      action  = "Block"
    }
  }

  # Brute force / OTP abuse (S.3): tight per-IP limit on auth endpoints.
  custom_rule {
    name                           = "RateLimitAuth"
    enabled                        = true
    priority                       = 10
    type                           = "RateLimitRule"
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = var.login_rate_limit_per_minute
    action                         = "Block"

    match_condition {
      match_variable = "RequestUri"
      operator       = "Contains"
      transforms     = ["Lowercase"]
      match_values   = ["/api/auth/login", "/api/auth/register", "/api/auth/unlock-account", "/api/2fa/", "otp"]
    }
  }

  custom_rule {
    name                           = "RateLimitApi"
    enabled                        = true
    priority                       = 20
    type                           = "RateLimitRule"
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = var.api_rate_limit_per_minute
    action                         = "Block"

    match_condition {
      match_variable = "RequestUri"
      operator       = "BeginsWith"
      transforms     = ["Lowercase"]
      match_values   = ["/api/"]
    }
  }

  # Interactive OpenAPI UI must never be public in prod (S.2 A05).
  custom_rule {
    name     = "BlockApiDocs"
    enabled  = true
    priority = 30
    type     = "MatchRule"
    action   = "Block"

    match_condition {
      match_variable = "RequestUri"
      operator       = "RegEx"
      transforms     = ["Lowercase"]
      match_values   = ["^https?://[^/]+/(docs|redoc|openapi\\.json)"]
    }
  }

  dynamic "custom_rule" {
    for_each = length(var.allowed_country_codes) > 0 ? [1] : []
    content {
      name     = "GeoAllowList"
      enabled  = true
      priority = 40
      type     = "MatchRule"
      action   = "Block"

      match_condition {
        match_variable     = "RemoteAddr"
        operator           = "GeoMatch"
        negation_condition = true
        match_values       = var.allowed_country_codes
      }
    }
  }
}

resource "azurerm_cdn_frontdoor_security_policy" "this" {
  name                     = "secpol-${var.name_prefix}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.this.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.this.id

      association {
        patterns_to_match = ["/*"]

        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.this.id
        }

        dynamic "domain" {
          for_each = azurerm_cdn_frontdoor_custom_domain.this
          content {
            cdn_frontdoor_domain_id = domain.value.id
          }
        }
      }
    }
  }
}

resource "azurerm_monitor_diagnostic_setting" "frontdoor" {
  name                       = "diag-to-log-analytics"
  target_resource_id         = azurerm_cdn_frontdoor_profile.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "FrontDoorAccessLog"
  }
  enabled_log {
    category = "FrontDoorWebApplicationFirewallLog"
  }
  enabled_log {
    category = "FrontDoorHealthProbeLog"
  }
}
