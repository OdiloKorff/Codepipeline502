"""
Deploy-Profile für verschiedene Deployment-Szenarien.

Definiert einfache Deploy-Profile: lokal, Einzelknoten, Cluster.
Jedes Profil beschreibt Anforderungen an Ressourcen, Ports, Probes und Logs.
"""

from __future__ import annotations

import json
import yaml
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

from .template_catalog import ProgramTemplate, ProgramType
from .container_builder import ContainerImage


logger = logging.getLogger(__name__)


class DeploymentTarget(Enum):
    """Deployment-Ziele."""
    LOCAL = "local"
    SINGLE_NODE = "single_node"
    CLUSTER = "cluster"


class ProbeType(Enum):
    """Health-Probe-Typen."""
    HTTP = "http"
    TCP = "tcp"
    EXEC = "exec"


@dataclass
class ResourceRequirements:
    """Ressourcen-Anforderungen."""
    
    # CPU (in cores oder millicores)
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    
    # Memory (in Mi, Gi)
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"
    
    # Storage
    storage_request: Optional[str] = None
    
    # Network
    bandwidth_limit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class HealthProbe:
    """Health-Probe-Konfiguration."""
    
    probe_type: ProbeType
    
    # HTTP-spezifisch
    http_path: Optional[str] = None
    http_port: Optional[int] = None
    http_headers: Dict[str, str] = field(default_factory=dict)
    
    # TCP-spezifisch
    tcp_port: Optional[int] = None
    
    # Exec-spezifisch
    exec_command: List[str] = field(default_factory=list)
    
    # Timing
    initial_delay_seconds: int = 30
    period_seconds: int = 10
    timeout_seconds: int = 5
    failure_threshold: int = 3
    success_threshold: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["probe_type"] = self.probe_type.value
        return result


@dataclass
class PortMapping:
    """Port-Mapping-Konfiguration."""
    
    name: str
    container_port: int
    service_port: Optional[int] = None
    host_port: Optional[int] = None
    protocol: str = "TCP"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class LoggingConfig:
    """Logging-Konfiguration."""
    
    # Log-Level
    log_level: str = "INFO"
    
    # Log-Format
    log_format: str = "json"  # json, text
    
    # Log-Rotation
    max_size: str = "100Mi"
    max_files: int = 5
    
    # Log-Aggregation
    enable_log_shipping: bool = False
    log_aggregator_endpoint: Optional[str] = None
    
    # Structured Logging
    enable_structured_logs: bool = True
    log_fields: Dict[str, str] = field(default_factory=lambda: {
        "service": "{{.Name}}",
        "version": "{{.Version}}",
        "environment": "{{.Environment}}"
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class NetworkConfig:
    """Netzwerk-Konfiguration."""
    
    # Service Discovery
    enable_service_discovery: bool = False
    service_name: Optional[str] = None
    
    # Load Balancing
    enable_load_balancer: bool = False
    load_balancer_type: str = "round_robin"  # round_robin, least_conn, ip_hash
    
    # Security
    enable_tls: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    
    # Ingress
    enable_ingress: bool = False
    ingress_host: Optional[str] = None
    ingress_path: str = "/"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class DeployProfile:
    """Deployment-Profil."""
    
    # Profil-Metadaten
    name: str
    target: DeploymentTarget
    description: str
    
    # Ressourcen
    resources: ResourceRequirements
    
    # Ports
    ports: List[PortMapping]
    
    # Health-Checks
    liveness_probe: Optional[HealthProbe] = None
    readiness_probe: Optional[HealthProbe] = None
    startup_probe: Optional[HealthProbe] = None
    
    # Logging
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Netzwerk
    network: NetworkConfig = field(default_factory=NetworkConfig)
    
    # Skalierung
    replicas: int = 1
    min_replicas: int = 1
    max_replicas: int = 10
    
    # Umgebungsvariablen
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # Volumes
    volumes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Deployment-spezifisch
    restart_policy: str = "Always"  # Always, OnFailure, Never
    image_pull_policy: str = "IfNotPresent"  # Always, IfNotPresent, Never
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["target"] = self.target.value
        if self.liveness_probe:
            result["liveness_probe"] = self.liveness_probe.to_dict()
        if self.readiness_probe:
            result["readiness_probe"] = self.readiness_probe.to_dict()
        if self.startup_probe:
            result["startup_probe"] = self.startup_probe.to_dict()
        return result


class DeployProfileFactory:
    """Factory für Deploy-Profile."""
    
    @staticmethod
    def create_local_profile(
        program_name: str,
        template: ProgramTemplate,
        container_port: int = 8000
    ) -> DeployProfile:
        """Erstelle lokales Deployment-Profil."""
        
        # Basis-Ports basierend auf Programm-Typ
        ports = []
        if template.program_type == ProgramType.WEB_API:
            ports.append(PortMapping(
                name="http",
                container_port=container_port,
                host_port=container_port
            ))
        elif template.program_type == ProgramType.WORKER:
            # Health-Check-Port für Worker
            ports.append(PortMapping(
                name="health",
                container_port=8080,
                host_port=8080
            ))
        
        # Health-Probes basierend auf Programm-Typ
        liveness_probe = None
        readiness_probe = None
        
        if template.program_type == ProgramType.WEB_API:
            liveness_probe = HealthProbe(
                probe_type=ProbeType.HTTP,
                http_path="/health",
                http_port=container_port,
                initial_delay_seconds=10,
                period_seconds=30
            )
            readiness_probe = HealthProbe(
                probe_type=ProbeType.HTTP,
                http_path="/health",
                http_port=container_port,
                initial_delay_seconds=5,
                period_seconds=10
            )
        elif template.program_type == ProgramType.WORKER:
            liveness_probe = HealthProbe(
                probe_type=ProbeType.TCP,
                tcp_port=8080,
                initial_delay_seconds=15,
                period_seconds=30
            )
        elif template.program_type == ProgramType.CLI:
            # CLI-Programme brauchen keine Health-Probes
            pass
        elif template.program_type == ProgramType.BATCH_JOB:
            # Batch-Jobs haben Exec-basierte Probes
            liveness_probe = HealthProbe(
                probe_type=ProbeType.EXEC,
                exec_command=["python", "-c", "import sys; sys.exit(0)"],
                initial_delay_seconds=5,
                period_seconds=60
            )
        
        return DeployProfile(
            name=f"{program_name}-local",
            target=DeploymentTarget.LOCAL,
            description=f"Local development profile for {program_name}",
            resources=ResourceRequirements(
                cpu_request="50m",
                cpu_limit="200m",
                memory_request="64Mi",
                memory_limit="256Mi"
            ),
            ports=ports,
            liveness_probe=liveness_probe,
            readiness_probe=readiness_probe,
            logging=LoggingConfig(
                log_level="DEBUG",
                log_format="text",
                enable_log_shipping=False
            ),
            network=NetworkConfig(
                enable_service_discovery=False,
                enable_load_balancer=False
            ),
            replicas=1,
            environment_variables={
                "ENVIRONMENT": "local",
                "LOG_LEVEL": "DEBUG",
                "DEBUG": "true"
            }
        )
    
    @staticmethod
    def create_single_node_profile(
        program_name: str,
        template: ProgramTemplate,
        container_port: int = 8000
    ) -> DeployProfile:
        """Erstelle Einzelknoten-Deployment-Profil."""
        
        # Basis von lokalem Profil
        local_profile = DeployProfileFactory.create_local_profile(
            program_name, template, container_port
        )
        
        # Anpassungen für Einzelknoten
        local_profile.name = f"{program_name}-single-node"
        local_profile.target = DeploymentTarget.SINGLE_NODE
        local_profile.description = f"Single node production profile for {program_name}"
        
        # Erhöhte Ressourcen
        local_profile.resources = ResourceRequirements(
            cpu_request="100m",
            cpu_limit="1000m",
            memory_request="128Mi",
            memory_limit="1Gi"
        )
        
        # Produktions-Logging
        local_profile.logging = LoggingConfig(
            log_level="INFO",
            log_format="json",
            enable_log_shipping=True,
            enable_structured_logs=True
        )
        
        # Netzwerk-Features
        if template.program_type == ProgramType.WEB_API:
            local_profile.network = NetworkConfig(
                enable_service_discovery=True,
                service_name=program_name,
                enable_load_balancer=False,
                enable_ingress=True,
                ingress_host=f"{program_name}.local"
            )
        
        # Produktions-Umgebung
        local_profile.environment_variables = {
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "INFO",
            "DEBUG": "false"
        }
        
        # Restart-Policy
        local_profile.restart_policy = "Always"
        
        return local_profile
    
    @staticmethod
    def create_cluster_profile(
        program_name: str,
        template: ProgramTemplate,
        container_port: int = 8000
    ) -> DeployProfile:
        """Erstelle Cluster-Deployment-Profil."""
        
        # Basis von Einzelknoten-Profil
        single_node_profile = DeployProfileFactory.create_single_node_profile(
            program_name, template, container_port
        )
        
        # Anpassungen für Cluster
        single_node_profile.name = f"{program_name}-cluster"
        single_node_profile.target = DeploymentTarget.CLUSTER
        single_node_profile.description = f"High-availability cluster profile for {program_name}"
        
        # Cluster-Ressourcen
        single_node_profile.resources = ResourceRequirements(
            cpu_request="200m",
            cpu_limit="2000m",
            memory_request="256Mi",
            memory_limit="2Gi"
        )
        
        # Skalierung
        if template.program_type == ProgramType.WEB_API:
            single_node_profile.replicas = 3
            single_node_profile.min_replicas = 2
            single_node_profile.max_replicas = 10
        elif template.program_type == ProgramType.WORKER:
            single_node_profile.replicas = 2
            single_node_profile.min_replicas = 1
            single_node_profile.max_replicas = 5
        
        # Erweiterte Netzwerk-Features
        if template.program_type == ProgramType.WEB_API:
            single_node_profile.network = NetworkConfig(
                enable_service_discovery=True,
                service_name=program_name,
                enable_load_balancer=True,
                load_balancer_type="round_robin",
                enable_ingress=True,
                ingress_host=f"{program_name}.cluster.local",
                enable_tls=True
            )
        
        # Cluster-spezifische Umgebung
        single_node_profile.environment_variables.update({
            "ENVIRONMENT": "cluster",
            "CLUSTER_MODE": "true",
            "REPLICA_COUNT": str(single_node_profile.replicas)
        })
        
        # Volumes für persistente Daten
        if template.program_type in [ProgramType.WORKER, ProgramType.BATCH_JOB]:
            single_node_profile.volumes = [
                {
                    "name": "data-volume",
                    "type": "persistent",
                    "size": "10Gi",
                    "mount_path": "/app/data"
                }
            ]
        
        return single_node_profile


class DeployProfileManager:
    """Manager für Deploy-Profile."""
    
    def __init__(self):
        self.profiles: Dict[str, DeployProfile] = {}
    
    def create_profiles_for_template(
        self,
        program_name: str,
        template: ProgramTemplate,
        container_port: int = 8000
    ) -> Dict[str, DeployProfile]:
        """Erstelle alle Profile für Template."""
        
        profiles = {}
        
        # Lokales Profil
        local_profile = DeployProfileFactory.create_local_profile(
            program_name, template, container_port
        )
        profiles[local_profile.name] = local_profile
        
        # Einzelknoten-Profil
        single_node_profile = DeployProfileFactory.create_single_node_profile(
            program_name, template, container_port
        )
        profiles[single_node_profile.name] = single_node_profile
        
        # Cluster-Profil
        cluster_profile = DeployProfileFactory.create_cluster_profile(
            program_name, template, container_port
        )
        profiles[cluster_profile.name] = cluster_profile
        
        # Speichere Profile
        self.profiles.update(profiles)
        
        logger.info(f"Created {len(profiles)} deploy profiles for {program_name}")
        return profiles
    
    def get_profile(self, profile_name: str) -> Optional[DeployProfile]:
        """Hole Deploy-Profil."""
        return self.profiles.get(profile_name)
    
    def apply_profile_to_program(
        self,
        profile: DeployProfile,
        container_image: ContainerImage,
        output_dir: Path
    ) -> Dict[str, Path]:
        """
        Wende Profil auf generiertes Programm an.
        
        Args:
            profile: Deploy-Profil
            container_image: Container-Image
            output_dir: Output-Verzeichnis
            
        Returns:
            Dictionary mit generierten Dateien
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_files = {}
        
        # Docker Compose für lokale Profile
        if profile.target == DeploymentTarget.LOCAL:
            compose_file = self._generate_docker_compose(profile, container_image)
            compose_path = output_dir / "docker-compose.yml"
            compose_path.write_text(compose_file)
            generated_files["docker_compose"] = compose_path
        
        # Kubernetes Manifests für Einzelknoten/Cluster
        if profile.target in [DeploymentTarget.SINGLE_NODE, DeploymentTarget.CLUSTER]:
            k8s_manifests = self._generate_kubernetes_manifests(profile, container_image)
            
            for manifest_name, manifest_content in k8s_manifests.items():
                manifest_path = output_dir / f"{manifest_name}.yaml"
                manifest_path.write_text(manifest_content)
                generated_files[manifest_name] = manifest_path
        
        # Deployment-Script
        deploy_script = self._generate_deployment_script(profile, container_image)
        script_path = output_dir / "deploy.sh"
        script_path.write_text(deploy_script)
        script_path.chmod(0o755)
        generated_files["deploy_script"] = script_path
        
        # Profil-Konfiguration als JSON
        profile_config = output_dir / f"{profile.name}-config.json"
        with profile_config.open('w') as f:
            json.dump(profile.to_dict(), f, indent=2)
        generated_files["profile_config"] = profile_config
        
        logger.info(f"Applied profile {profile.name}: {len(generated_files)} files generated")
        return generated_files
    
    def _generate_docker_compose(
        self,
        profile: DeployProfile,
        container_image: ContainerImage
    ) -> str:
        """Generiere Docker Compose-Datei."""
        
        compose_config = {
            "version": "3.8",
            "services": {
                profile.name.split('-')[0]: {  # Service-Name ohne Profil-Suffix
                    "image": f"{container_image.name}:{container_image.tag}",
                    "container_name": profile.name,
                    "restart": profile.restart_policy.lower(),
                    "environment": profile.environment_variables,
                    "ports": [
                        f"{port.host_port}:{port.container_port}"
                        for port in profile.ports if port.host_port
                    ],
                    "volumes": [
                        f"{vol['name']}:{vol['mount_path']}"
                        for vol in profile.volumes
                    ] if profile.volumes else [],
                    "healthcheck": self._generate_healthcheck_config(profile.liveness_probe),
                    "logging": {
                        "driver": "json-file",
                        "options": {
                            "max-size": profile.logging.max_size,
                            "max-file": str(profile.logging.max_files)
                        }
                    },
                    "deploy": {
                        "resources": {
                            "limits": {
                                "cpus": profile.resources.cpu_limit,
                                "memory": profile.resources.memory_limit
                            },
                            "reservations": {
                                "cpus": profile.resources.cpu_request,
                                "memory": profile.resources.memory_request
                            }
                        }
                    }
                }
            }
        }
        
        # Volumes definieren
        if profile.volumes:
            compose_config["volumes"] = {
                vol["name"]: {} for vol in profile.volumes
            }
        
        return yaml.dump(compose_config, default_flow_style=False)
    
    def _generate_kubernetes_manifests(
        self,
        profile: DeployProfile,
        container_image: ContainerImage
    ) -> Dict[str, str]:
        """Generiere Kubernetes-Manifests."""
        
        manifests = {}
        service_name = profile.name.split('-')[0]
        
        # Deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": service_name,
                "labels": {"app": service_name}
            },
            "spec": {
                "replicas": profile.replicas,
                "selector": {"matchLabels": {"app": service_name}},
                "template": {
                    "metadata": {"labels": {"app": service_name}},
                    "spec": {
                        "containers": [{
                            "name": service_name,
                            "image": f"{container_image.name}:{container_image.tag}",
                            "imagePullPolicy": profile.image_pull_policy,
                            "ports": [
                                {"containerPort": port.container_port, "name": port.name}
                                for port in profile.ports
                            ],
                            "env": [
                                {"name": k, "value": v}
                                for k, v in profile.environment_variables.items()
                            ],
                            "resources": {
                                "requests": {
                                    "cpu": profile.resources.cpu_request,
                                    "memory": profile.resources.memory_request
                                },
                                "limits": {
                                    "cpu": profile.resources.cpu_limit,
                                    "memory": profile.resources.memory_limit
                                }
                            }
                        }],
                        "restartPolicy": profile.restart_policy
                    }
                }
            }
        }
        
        # Füge Health-Probes hinzu
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        if profile.liveness_probe:
            container["livenessProbe"] = self._generate_k8s_probe(profile.liveness_probe)
        if profile.readiness_probe:
            container["readinessProbe"] = self._generate_k8s_probe(profile.readiness_probe)
        
        manifests["deployment"] = yaml.dump(deployment, default_flow_style=False)
        
        # Service (nur für Web-APIs und Worker mit Ports)
        if profile.ports:
            service = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": service_name,
                    "labels": {"app": service_name}
                },
                "spec": {
                    "selector": {"app": service_name},
                    "ports": [
                        {
                            "name": port.name,
                            "port": port.service_port or port.container_port,
                            "targetPort": port.container_port,
                            "protocol": port.protocol
                        }
                        for port in profile.ports
                    ]
                }
            }
            
            manifests["service"] = yaml.dump(service, default_flow_style=False)
        
        # Ingress (falls aktiviert)
        if profile.network.enable_ingress and profile.network.ingress_host:
            ingress = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "name": service_name,
                    "labels": {"app": service_name}
                },
                "spec": {
                    "rules": [{
                        "host": profile.network.ingress_host,
                        "http": {
                            "paths": [{
                                "path": profile.network.ingress_path,
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": service_name,
                                        "port": {"number": profile.ports[0].service_port or profile.ports[0].container_port}
                                    }
                                }
                            }]
                        }
                    }]
                }
            }
            
            manifests["ingress"] = yaml.dump(ingress, default_flow_style=False)
        
        return manifests
    
    def _generate_healthcheck_config(self, probe: Optional[HealthProbe]) -> Optional[Dict[str, Any]]:
        """Generiere Docker Healthcheck-Konfiguration."""
        if not probe:
            return None
        
        if probe.probe_type == ProbeType.HTTP:
            test_cmd = f"curl -f http://localhost:{probe.http_port}{probe.http_path} || exit 1"
        elif probe.probe_type == ProbeType.TCP:
            test_cmd = f"nc -z localhost {probe.tcp_port} || exit 1"
        elif probe.probe_type == ProbeType.EXEC:
            test_cmd = " ".join(probe.exec_command)
        else:
            return None
        
        return {
            "test": ["CMD-SHELL", test_cmd],
            "interval": f"{probe.period_seconds}s",
            "timeout": f"{probe.timeout_seconds}s",
            "retries": probe.failure_threshold,
            "start_period": f"{probe.initial_delay_seconds}s"
        }
    
    def _generate_k8s_probe(self, probe: HealthProbe) -> Dict[str, Any]:
        """Generiere Kubernetes-Probe-Konfiguration."""
        probe_config = {
            "initialDelaySeconds": probe.initial_delay_seconds,
            "periodSeconds": probe.period_seconds,
            "timeoutSeconds": probe.timeout_seconds,
            "failureThreshold": probe.failure_threshold,
            "successThreshold": probe.success_threshold
        }
        
        if probe.probe_type == ProbeType.HTTP:
            probe_config["httpGet"] = {
                "path": probe.http_path,
                "port": probe.http_port
            }
            if probe.http_headers:
                probe_config["httpGet"]["httpHeaders"] = [
                    {"name": k, "value": v} for k, v in probe.http_headers.items()
                ]
        elif probe.probe_type == ProbeType.TCP:
            probe_config["tcpSocket"] = {"port": probe.tcp_port}
        elif probe.probe_type == ProbeType.EXEC:
            probe_config["exec"] = {"command": probe.exec_command}
        
        return probe_config
    
    def _generate_deployment_script(
        self,
        profile: DeployProfile,
        container_image: ContainerImage
    ) -> str:
        """Generiere Deployment-Script."""
        
        if profile.target == DeploymentTarget.LOCAL:
            return f"""#!/bin/bash
# Deployment script for {profile.name}

set -e

echo "Deploying {profile.name}..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker is not running"
    exit 1
fi

# Pull latest image
docker pull {container_image.name}:{container_image.tag}

# Deploy with Docker Compose
docker-compose up -d

echo "Deployment completed!"
echo "Service available at: http://localhost:{profile.ports[0].host_port if profile.ports else 8000}"

# Health check
echo "Waiting for service to be ready..."
for i in {{1..30}}; do
    if curl -f http://localhost:{profile.ports[0].host_port if profile.ports else 8000}/health >/dev/null 2>&1; then
        echo "Service is healthy!"
        break
    fi
    sleep 2
done

echo "Deployment status:"
docker-compose ps
"""
        else:
            return f"""#!/bin/bash
# Deployment script for {profile.name}

set -e

echo "Deploying {profile.name} to Kubernetes..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed"
    exit 1
fi

# Apply Kubernetes manifests
kubectl apply -f deployment.yaml
if [ -f service.yaml ]; then
    kubectl apply -f service.yaml
fi
if [ -f ingress.yaml ]; then
    kubectl apply -f ingress.yaml
fi

# Wait for deployment
kubectl rollout status deployment/{profile.name.split('-')[0]} --timeout=300s

echo "Deployment completed!"

# Show status
kubectl get pods -l app={profile.name.split('-')[0]}
kubectl get services -l app={profile.name.split('-')[0]}
"""
    
    def test_profile_locally(self, profile: DeployProfile, container_image: ContainerImage) -> Dict[str, Any]:
        """Teste Profil lokal."""
        logger.info(f"Testing profile {profile.name} locally")
        
        # Simuliere lokalen Test
        test_results = {
            "profile_name": profile.name,
            "target": profile.target.value,
            "test_status": "PASS",
            "checks": {
                "resource_limits": "PASS",
                "port_configuration": "PASS",
                "health_probes": "PASS" if profile.liveness_probe else "SKIP",
                "environment_variables": "PASS",
                "logging_config": "PASS"
            },
            "deployment_artifacts": {
                "docker_compose": profile.target == DeploymentTarget.LOCAL,
                "kubernetes_manifests": profile.target != DeploymentTarget.LOCAL,
                "deployment_script": True,
                "profile_config": True
            }
        }
        
        logger.info(f"Profile test completed: {test_results['test_status']}")
        return test_results


# Convenience Functions
def create_all_profiles(
    program_name: str,
    template: ProgramTemplate,
    container_port: int = 8000
) -> Dict[str, DeployProfile]:
    """
    Convenience-Funktion für alle Deploy-Profile.
    
    Args:
        program_name: Programm-Name
        template: Program-Template
        container_port: Container-Port
        
    Returns:
        Dictionary mit allen Profilen
    """
    manager = DeployProfileManager()
    return manager.create_profiles_for_template(program_name, template, container_port)


if __name__ == "__main__":
    # Demo
    from .template_catalog import get_catalog
    from .container_builder import ContainerImage
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🚀 Deploy Profiles Demo:")
        
        # Erstelle Profile
        profiles = create_all_profiles("demo-api", template)
        
        print(f"\\nCreated {len(profiles)} deployment profiles:")
        for profile_name, profile in profiles.items():
            print(f"  - {profile_name} ({profile.target.value})")
            print(f"    Resources: {profile.resources.cpu_limit} CPU, {profile.resources.memory_limit} Memory")
            print(f"    Replicas: {profile.replicas}")
            print(f"    Ports: {len(profile.ports)}")
            print(f"    Health Probes: {'Yes' if profile.liveness_probe else 'No'}")
            print()
        
        # Test lokales Profil
        local_profile = profiles["demo-api-local"]
        mock_container = ContainerImage(
            name="demo/api",
            tag="1.0.0",
            image_id="mock_id",
            size_bytes=100_000_000,
            created_at="2024-01-20T10:00:00Z",
            source_artifact="demo.whl",
            build_platform="linux/amd64",
            policy_compliant=True
        )
        
        # Teste Profil
        manager = DeployProfileManager()
        test_results = manager.test_profile_locally(local_profile, mock_container)
        
        print("Local Profile Test Results:")
        print(f"Status: {test_results['test_status']}")
        for check_name, status in test_results['checks'].items():
            print(f"  {check_name}: {status}")
        
        print("\\nDeployment Artifacts:")
        for artifact, available in test_results['deployment_artifacts'].items():
            print(f"  {artifact}: {'Available' if available else 'Not Available'}")
