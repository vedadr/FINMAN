variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region. Must be one of the three free-tier eligible regions."
  type        = string
  default     = "us-central1"

  validation {
    condition     = contains(["us-west1", "us-central1", "us-east1"], var.region)
    error_message = "Region must be us-west1, us-central1, or us-east1 to qualify for the GCP free tier."
  }
}

variable "zone" {
  description = "GCP zone within the chosen region (e.g. us-central1-a)."
  type        = string
  default     = "us-central1-a"
}

variable "app_port" {
  description = "Port the Streamlit app listens on."
  type        = number
  default     = 8501
}

variable "repo_url" {
  description = "Git repository URL to clone onto the VM. Leave empty to skip cloning (deploy manually via gcloud scp)."
  type        = string
  default     = ""
}

# ── Secrets (marked sensitive — never printed in plan output) ─────────────────

variable "openai_api_key" {
  description = "OpenAI API key."
  type        = string
  sensitive   = true
}

variable "supabase_url" {
  description = "Supabase project URL (https://<ref>.supabase.co)."
  type        = string
  sensitive   = true
}

variable "supabase_publishable_key" {
  description = "Supabase publishable (anon) API key."
  type        = string
  sensitive   = true
}

variable "supabase_secret_key" {
  description = "Supabase secret API key."
  type        = string
  sensitive   = true
}

variable "supabase_db_url" {
  description = "Direct Postgres connection URL for the Supabase database (used by dbt and the agent)."
  type        = string
  sensitive   = true
}
