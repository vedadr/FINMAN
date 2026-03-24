terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.5"
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ── Compute instance ──────────────────────────────────────────────────────────
# e2-micro + 30 GB pd-standard in a free-tier region = $0/month on GCP free tier.

resource "google_compute_instance" "finman" {
  name         = "finman-app"
  machine_type = "e2-micro"
  zone         = var.zone

  tags = ["finman-app"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 30        # GB — full free-tier allowance
      type  = "pd-standard"  # pd-ssd is NOT covered by free tier
    }
  }

  network_interface {
    network = "default"

    # Ephemeral external IP — no charge when attached to a running instance.
    # Replace with google_compute_address resource if you need a static IP.
    access_config {}
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      repo_url                 = var.repo_url
      app_port                 = var.app_port
      openai_api_key           = var.openai_api_key
      supabase_url             = var.supabase_url
      supabase_publishable_key = var.supabase_publishable_key
      supabase_secret_key      = var.supabase_secret_key
      supabase_db_url          = var.supabase_db_url
    })
  }

  # Allow the VM to call GCP APIs (e.g. Cloud Logging, Secret Manager if added later)
  service_account {
    scopes = ["cloud-platform"]
  }

  # Ensure instance is not preemptible — required for free-tier eligibility
  scheduling {
    preemptible       = false
    automatic_restart = true
  }

  lifecycle {
    # Prevent accidental deletion of the VM (and its disk data)
    prevent_destroy = true
  }
}

# ── Firewall: Streamlit app port ──────────────────────────────────────────────

resource "google_compute_firewall" "finman_app" {
  name    = "allow-finman-app"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = [tostring(var.app_port)]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["finman-app"]

  description = "Allow inbound traffic to the FINMAN Streamlit app."
}

# ── Firewall: SSH ─────────────────────────────────────────────────────────────
# The default GCP network already includes a default-allow-ssh rule.
# This resource makes it explicit and tag-scoped for this instance.

resource "google_compute_firewall" "finman_ssh" {
  name    = "allow-finman-ssh"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["finman-app"]

  description = "Allow SSH to the FINMAN instance."
}
