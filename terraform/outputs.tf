output "instance_name" {
  description = "Name of the Compute Engine instance."
  value       = google_compute_instance.finman.name
}

output "external_ip" {
  description = "External IP address of the FINMAN instance."
  value       = google_compute_instance.finman.network_interface[0].access_config[0].nat_ip
}

output "app_url" {
  description = "URL to access the FINMAN Streamlit app."
  value       = "http://${google_compute_instance.finman.network_interface[0].access_config[0].nat_ip}:${var.app_port}"
}

output "ssh_command" {
  description = "Command to SSH into the instance."
  value       = "gcloud compute ssh finman-app --zone=${var.zone} --project=${var.project_id}"
}

output "deploy_command" {
  description = "Command to copy app files to the instance (run from the FINMAN repo root)."
  value       = "gcloud compute scp --recurse ./agent finman-app:/opt/finman/ --zone=${var.zone} --project=${var.project_id}"
}

output "startup_log_command" {
  description = "Command to tail the startup script log on the instance."
  value       = "gcloud compute ssh finman-app --zone=${var.zone} --project=${var.project_id} --command='sudo tail -f /var/log/finman-startup.log'"
}
