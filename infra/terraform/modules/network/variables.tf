variable "name_prefix" {
  description = "Prefix such as airyatra-prod-cin used in every resource name."
  type        = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "address_space" {
  description = "VNet CIDR. A /16 leaves room for the 20K-user stage."
  type        = string
}
variable "tags" {
  type    = map(string)
  default = {}
}
variable "app_service_subnet_enabled" {
  description = "Add a subnet delegated to App Service and let it reach the private endpoints."
  type        = bool
  default     = false
}
