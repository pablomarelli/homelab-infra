variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit permissions"
  type = string
  sensitive = true
}

variable "domain" {
  description = "Root domain"
  type = string
  default = "pablomarelli.dev"
}

variable "tunnel_id" {
  description = "Cloudflare Tunnel ID"
  type = string
  default = "4d2e246b-8c39-49cd-b89c-5ba89d0fd598"
}

variable "subdomains" {
  description = "Subdomains to route through the tunnel"
  type = list(string)
  default = ["argocd", "portfolio", "finance", "home", "auth", "status", "analytics", "grafana"]
}
