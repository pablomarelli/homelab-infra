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
  default = "adcf61e7-1183-4ff4-9f77-b25fa8fed5fd"
}

variable "subdomains" {
  description = "Subdomains to route through the tunnel"
  type = list(string)
  default = ["argocd", "portfolio", "finance", "home", "auth", "status", "analytics", "grafana"]
}
