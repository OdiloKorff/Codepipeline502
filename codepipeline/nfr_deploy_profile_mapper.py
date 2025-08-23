"""
NFR-Interpretation wirkt auf Deploy-Profile.

Implementiert:
- Interpretation von Latenz- und Durchsatzklassen
- Automatische Einstellung von Timeouts, Concurrency, Probe-Intervalle
- Messbare E2E-Unterschiede bei geänderten NFRs
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class LatencyClass(Enum):
    """Latenz-Klassen."""
    ULTRA_LOW = "ultra_low"      # < 10ms
    LOW = "low"                  # < 100ms
    MEDIUM = "medium"            # < 500ms
    HIGH = "high"                # < 2000ms
    RELAXED = "relaxed"          # > 2000ms


class ThroughputClass(Enum):
    """Durchsatz-Klassen."""
    ULTRA_HIGH = "ultra_high"    # > 10000 req/s
    HIGH = "high"                # > 1000 req/s
    MEDIUM = "medium"            # > 100 req/s
    LOW = "low"                  # > 10 req/s
    MINIMAL = "minimal"          # < 10 req/s


class AvailabilityClass(Enum):
    """Verfügbarkeits-Klassen."""
    CRITICAL = "critical"        # 99.99%
    HIGH = "high"                # 99.9%
    STANDARD = "standard"        # 99.5%
    BASIC = "basic"              # 99%
    DEVELOPMENT = "development"  # < 99%


@dataclass
class NFRProfile:
    """Non-Functional Requirements Profile."""
    
    # Latenz-Anforderungen
    latency_class: LatencyClass = LatencyClass.MEDIUM
    max_response_time_ms: int = 500
    p95_response_time_ms: int = 200
    
    # Durchsatz-Anforderungen
    throughput_class: ThroughputClass = ThroughputClass.MEDIUM
    target_rps: int = 100
    peak_rps: int = 300
    
    # Verfügbarkeits-Anforderungen
    availability_class: AvailabilityClass = AvailabilityClass.STANDARD
    target_uptime_percent: float = 99.5
    max_downtime_minutes_per_month: int = 216
    
    # Skalierungs-Anforderungen
    min_instances: int = 1
    max_instances: int = 5
    scale_up_threshold: float = 70.0  # CPU %
    scale_down_threshold: float = 30.0  # CPU %
    
    # Ressourcen-Anforderungen
    cpu_cores: float = 1.0
    memory_mb: int = 512
    storage_mb: int = 1024
    
    # Performance-Budget
    startup_time_max_seconds: int = 30
    health_check_timeout_seconds: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "latency_class": self.latency_class.value,
            "max_response_time_ms": self.max_response_time_ms,
            "p95_response_time_ms": self.p95_response_time_ms,
            "throughput_class": self.throughput_class.value,
            "target_rps": self.target_rps,
            "peak_rps": self.peak_rps,
            "availability_class": self.availability_class.value,
            "target_uptime_percent": self.target_uptime_percent,
            "max_downtime_minutes_per_month": self.max_downtime_minutes_per_month,
            "min_instances": self.min_instances,
            "max_instances": self.max_instances,
            "scale_up_threshold": self.scale_up_threshold,
            "scale_down_threshold": self.scale_down_threshold,
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "storage_mb": self.storage_mb,
            "startup_time_max_seconds": self.startup_time_max_seconds,
            "health_check_timeout_seconds": self.health_check_timeout_seconds
        }


@dataclass
class DeploymentConfiguration:
    """Deployment-Konfiguration basierend auf NFRs."""
    
    # Container-Konfiguration
    cpu_limit: str = "1000m"
    cpu_request: str = "500m"
    memory_limit: str = "512Mi"
    memory_request: str = "256Mi"
    
    # Replikas und Skalierung
    replicas: int = 2
    min_replicas: int = 1
    max_replicas: int = 5
    target_cpu_utilization: int = 70
    
    # Health Checks
    readiness_probe_initial_delay: int = 10
    readiness_probe_period: int = 10
    readiness_probe_timeout: int = 5
    readiness_probe_failure_threshold: int = 3
    
    liveness_probe_initial_delay: int = 30
    liveness_probe_period: int = 30
    liveness_probe_timeout: int = 10
    liveness_probe_failure_threshold: int = 3
    
    # Service-Konfiguration
    service_timeout_seconds: int = 30
    connection_timeout_seconds: int = 10
    keep_alive_timeout_seconds: int = 65
    
    # Load Balancer
    load_balancer_algorithm: str = "round_robin"  # round_robin, least_conn, ip_hash
    session_affinity: bool = False
    
    # Monitoring
    metrics_enabled: bool = True
    logging_level: str = "INFO"
    trace_sampling_rate: float = 0.1
    
    # Rolling Update
    max_unavailable: str = "25%"
    max_surge: str = "25%"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "cpu_limit": self.cpu_limit,
            "cpu_request": self.cpu_request,
            "memory_limit": self.memory_limit,
            "memory_request": self.memory_request,
            "replicas": self.replicas,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "target_cpu_utilization": self.target_cpu_utilization,
            "readiness_probe_initial_delay": self.readiness_probe_initial_delay,
            "readiness_probe_period": self.readiness_probe_period,
            "readiness_probe_timeout": self.readiness_probe_timeout,
            "readiness_probe_failure_threshold": self.readiness_probe_failure_threshold,
            "liveness_probe_initial_delay": self.liveness_probe_initial_delay,
            "liveness_probe_period": self.liveness_probe_period,
            "liveness_probe_timeout": self.liveness_probe_timeout,
            "liveness_probe_failure_threshold": self.liveness_probe_failure_threshold,
            "service_timeout_seconds": self.service_timeout_seconds,
            "connection_timeout_seconds": self.connection_timeout_seconds,
            "keep_alive_timeout_seconds": self.keep_alive_timeout_seconds,
            "load_balancer_algorithm": self.load_balancer_algorithm,
            "session_affinity": self.session_affinity,
            "metrics_enabled": self.metrics_enabled,
            "logging_level": self.logging_level,
            "trace_sampling_rate": self.trace_sampling_rate,
            "max_unavailable": self.max_unavailable,
            "max_surge": self.max_surge
        }


class NFRParser:
    """Parser für NFR-Extraktion aus natürlichsprachlichen Prompts."""
    
    def __init__(self):
        # Latenz-Pattern
        self.latency_patterns = [
            (r"ultra.?low.?latency|latency.*<.*10.*ms|response.*<.*10.*ms", LatencyClass.ULTRA_LOW, 10),
            (r"low.?latency|fast.?response|latency.*<.*100.*ms|response.*<.*100.*ms", LatencyClass.LOW, 100),
            (r"medium.?latency|normal.?response|latency.*<.*500.*ms|response.*<.*500.*ms", LatencyClass.MEDIUM, 500),
            (r"high.?latency|slow.?response|latency.*<.*2.*s|response.*<.*2.*s", LatencyClass.HIGH, 2000),
            (r"relaxed.?latency|batch.?processing|background.*task", LatencyClass.RELAXED, 5000)
        ]
        
        # Durchsatz-Pattern
        self.throughput_patterns = [
            (r"ultra.?high.?throughput|>.*10000.*req|>.*10k.*req", ThroughputClass.ULTRA_HIGH, 10000),
            (r"high.?throughput|>.*1000.*req|>.*1k.*req", ThroughputClass.HIGH, 1000),
            (r"medium.?throughput|>.*100.*req", ThroughputClass.MEDIUM, 100),
            (r"low.?throughput|>.*10.*req", ThroughputClass.LOW, 10),
            (r"minimal.?throughput|few.*requests|single.*user", ThroughputClass.MINIMAL, 5)
        ]
        
        # Verfügbarkeits-Pattern
        self.availability_patterns = [
            (r"critical.?availability|99\\.99|four.?nines", AvailabilityClass.CRITICAL, 99.99),
            (r"high.?availability|99\\.9|three.?nines", AvailabilityClass.HIGH, 99.9),
            (r"standard.?availability|99\\.5", AvailabilityClass.STANDARD, 99.5),
            (r"basic.?availability|99\\.|uptime", AvailabilityClass.BASIC, 99.0),
            (r"development|prototype|testing", AvailabilityClass.DEVELOPMENT, 95.0)
        ]
        
        # Skalierungs-Pattern
        self.scaling_patterns = [
            (r"auto.?scal|elastic|dynamic.*scaling", True),
            (r"fixed.*size|static.*deployment|single.*instance", False)
        ]
        
        # Ressourcen-Pattern
        self.resource_patterns = [
            (r"cpu.?intensive|compute.?heavy|processing", "cpu_intensive"),
            (r"memory.?intensive|large.?dataset|caching", "memory_intensive"),
            (r"io.?intensive|database|file.?processing", "io_intensive"),
            (r"lightweight|minimal.*resources|small.*footprint", "lightweight")
        ]
    
    def parse_nfr_from_prompt(self, prompt: str) -> NFRProfile:
        """Extrahiere NFR-Profile aus Prompt."""
        
        prompt_lower = prompt.lower()
        
        # Standard-Profile
        nfr_profile = NFRProfile()
        
        # Parse Latenz
        for pattern, latency_class, max_ms in self.latency_patterns:
            if re.search(pattern, prompt_lower):
                nfr_profile.latency_class = latency_class
                nfr_profile.max_response_time_ms = max_ms
                nfr_profile.p95_response_time_ms = int(max_ms * 0.8)
                break
        
        # Parse Durchsatz
        for pattern, throughput_class, target_rps in self.throughput_patterns:
            if re.search(pattern, prompt_lower):
                nfr_profile.throughput_class = throughput_class
                nfr_profile.target_rps = target_rps
                nfr_profile.peak_rps = int(target_rps * 3)
                break
        
        # Parse Verfügbarkeit
        for pattern, availability_class, uptime_percent in self.availability_patterns:
            if re.search(pattern, prompt_lower):
                nfr_profile.availability_class = availability_class
                nfr_profile.target_uptime_percent = uptime_percent
                
                # Berechne Downtime
                downtime_minutes = (100 - uptime_percent) / 100 * 30 * 24 * 60  # pro Monat
                nfr_profile.max_downtime_minutes_per_month = int(downtime_minutes)
                break
        
        # Parse Skalierung
        auto_scaling = False
        for pattern, scaling_enabled in self.scaling_patterns:
            if re.search(pattern, prompt_lower):
                auto_scaling = scaling_enabled
                break
        
        if auto_scaling:
            nfr_profile.min_instances = 2
            nfr_profile.max_instances = 10
        else:
            nfr_profile.min_instances = 1
            nfr_profile.max_instances = 3
        
        # Parse Ressourcen-Anforderungen
        for pattern, resource_type in self.resource_patterns:
            if re.search(pattern, prompt_lower):
                if resource_type == "cpu_intensive":
                    nfr_profile.cpu_cores = 2.0
                    nfr_profile.memory_mb = 1024
                elif resource_type == "memory_intensive":
                    nfr_profile.cpu_cores = 1.0
                    nfr_profile.memory_mb = 2048
                elif resource_type == "io_intensive":
                    nfr_profile.cpu_cores = 1.5
                    nfr_profile.memory_mb = 1024
                    nfr_profile.storage_mb = 4096
                elif resource_type == "lightweight":
                    nfr_profile.cpu_cores = 0.5
                    nfr_profile.memory_mb = 256
                    nfr_profile.storage_mb = 512
                break
        
        # Extrahiere spezifische Zahlen falls vorhanden
        self._extract_specific_values(prompt_lower, nfr_profile)
        
        return nfr_profile
    
    def _extract_specific_values(self, prompt: str, nfr_profile: NFRProfile):
        """Extrahiere spezifische Zahlen-Werte aus Prompt."""
        
        # Latenz-Werte
        latency_match = re.search(r"latency.*?(\d+)\s*(ms|milliseconds?)", prompt)
        if latency_match:
            nfr_profile.max_response_time_ms = int(latency_match.group(1))
        
        response_time_match = re.search(r"response.*?time.*?(\d+)\s*(ms|milliseconds?)", prompt)
        if response_time_match:
            nfr_profile.max_response_time_ms = int(response_time_match.group(1))
        
        # Durchsatz-Werte
        rps_match = re.search(r"(\d+)\s*(rps|req.*?per.*?second|requests.*?per.*?second)", prompt)
        if rps_match:
            nfr_profile.target_rps = int(rps_match.group(1))
            nfr_profile.peak_rps = int(nfr_profile.target_rps * 3)
        
        # CPU-Werte
        cpu_match = re.search(r"(\d+(?:\.\d+)?)\s*(cpu|cores?)", prompt)
        if cpu_match:
            nfr_profile.cpu_cores = float(cpu_match.group(1))
        
        # Memory-Werte
        memory_match = re.search(r"(\d+)\s*(mb|gb|megabytes?|gigabytes?)", prompt)
        if memory_match:
            value = int(memory_match.group(1))
            unit = memory_match.group(2).lower()
            
            if unit.startswith('g'):
                nfr_profile.memory_mb = value * 1024
            else:
                nfr_profile.memory_mb = value


class DeploymentMapper:
    """Mapper von NFR-Profile zu Deployment-Konfiguration."""
    
    def __init__(self):
        pass
    
    def map_nfr_to_deployment(self, nfr_profile: NFRProfile) -> DeploymentConfiguration:
        """Mappe NFR-Profile zu Deployment-Konfiguration."""
        
        config = DeploymentConfiguration()
        
        # CPU und Memory basierend auf NFR
        config.cpu_request = f"{int(nfr_profile.cpu_cores * 500)}m"
        config.cpu_limit = f"{int(nfr_profile.cpu_cores * 1000)}m"
        config.memory_request = f"{nfr_profile.memory_mb // 2}Mi"
        config.memory_limit = f"{nfr_profile.memory_mb}Mi"
        
        # Replikas basierend auf Verfügbarkeit und Durchsatz
        if nfr_profile.availability_class in [AvailabilityClass.CRITICAL, AvailabilityClass.HIGH]:
            config.replicas = max(3, nfr_profile.min_instances)
            config.min_replicas = max(2, nfr_profile.min_instances)
        else:
            config.replicas = max(2, nfr_profile.min_instances)
            config.min_replicas = nfr_profile.min_instances
        
        config.max_replicas = nfr_profile.max_instances
        config.target_cpu_utilization = int(nfr_profile.scale_up_threshold)
        
        # Health Checks basierend auf Latenz-Klasse
        self._configure_health_checks(config, nfr_profile)
        
        # Service Timeouts basierend auf Latenz
        self._configure_service_timeouts(config, nfr_profile)
        
        # Load Balancer basierend auf Durchsatz
        self._configure_load_balancer(config, nfr_profile)
        
        # Monitoring basierend auf Verfügbarkeit
        self._configure_monitoring(config, nfr_profile)
        
        # Rolling Update basierend auf Verfügbarkeit
        self._configure_rolling_update(config, nfr_profile)
        
        return config
    
    def _configure_health_checks(self, config: DeploymentConfiguration, nfr_profile: NFRProfile):
        """Konfiguriere Health Checks."""
        
        # Aggressive Health Checks für niedrige Latenz
        if nfr_profile.latency_class in [LatencyClass.ULTRA_LOW, LatencyClass.LOW]:
            config.readiness_probe_initial_delay = 5
            config.readiness_probe_period = 5
            config.readiness_probe_timeout = 2
            config.readiness_probe_failure_threshold = 2
            
            config.liveness_probe_initial_delay = 15
            config.liveness_probe_period = 15
            config.liveness_probe_timeout = 5
            config.liveness_probe_failure_threshold = 2
        
        # Relaxed Health Checks für hohe Latenz
        elif nfr_profile.latency_class == LatencyClass.RELAXED:
            config.readiness_probe_initial_delay = 30
            config.readiness_probe_period = 30
            config.readiness_probe_timeout = 15
            config.readiness_probe_failure_threshold = 5
            
            config.liveness_probe_initial_delay = 60
            config.liveness_probe_period = 60
            config.liveness_probe_timeout = 30
            config.liveness_probe_failure_threshold = 5
        
        # Standard für Medium/High
        else:
            config.readiness_probe_initial_delay = 10
            config.readiness_probe_period = 10
            config.readiness_probe_timeout = 5
            config.readiness_probe_failure_threshold = 3
            
            config.liveness_probe_initial_delay = 30
            config.liveness_probe_period = 30
            config.liveness_probe_timeout = 10
            config.liveness_probe_failure_threshold = 3
    
    def _configure_service_timeouts(self, config: DeploymentConfiguration, nfr_profile: NFRProfile):
        """Konfiguriere Service Timeouts."""
        
        base_timeout = nfr_profile.max_response_time_ms // 1000  # Convert to seconds
        
        config.service_timeout_seconds = max(5, base_timeout * 2)
        config.connection_timeout_seconds = max(2, base_timeout)
        config.keep_alive_timeout_seconds = max(30, base_timeout * 10)
    
    def _configure_load_balancer(self, config: DeploymentConfiguration, nfr_profile: NFRProfile):
        """Konfiguriere Load Balancer."""
        
        # High throughput -> least connections
        if nfr_profile.throughput_class in [ThroughputClass.ULTRA_HIGH, ThroughputClass.HIGH]:
            config.load_balancer_algorithm = "least_conn"
            config.session_affinity = False
        
        # Medium throughput -> round robin
        elif nfr_profile.throughput_class == ThroughputClass.MEDIUM:
            config.load_balancer_algorithm = "round_robin"
            config.session_affinity = False
        
        # Low throughput -> might benefit from session affinity
        else:
            config.load_balancer_algorithm = "ip_hash"
            config.session_affinity = True
    
    def _configure_monitoring(self, config: DeploymentConfiguration, nfr_profile: NFRProfile):
        """Konfiguriere Monitoring."""
        
        # High availability -> detailed monitoring
        if nfr_profile.availability_class in [AvailabilityClass.CRITICAL, AvailabilityClass.HIGH]:
            config.metrics_enabled = True
            config.logging_level = "INFO"
            config.trace_sampling_rate = 0.5
        
        # Standard availability
        elif nfr_profile.availability_class == AvailabilityClass.STANDARD:
            config.metrics_enabled = True
            config.logging_level = "INFO"
            config.trace_sampling_rate = 0.1
        
        # Development/Basic
        else:
            config.metrics_enabled = True
            config.logging_level = "WARN"
            config.trace_sampling_rate = 0.01
    
    def _configure_rolling_update(self, config: DeploymentConfiguration, nfr_profile: NFRProfile):
        """Konfiguriere Rolling Update."""
        
        # Critical availability -> conservative updates
        if nfr_profile.availability_class == AvailabilityClass.CRITICAL:
            config.max_unavailable = "10%"
            config.max_surge = "10%"
        
        # High availability -> moderate updates
        elif nfr_profile.availability_class == AvailabilityClass.HIGH:
            config.max_unavailable = "20%"
            config.max_surge = "20%"
        
        # Standard and below -> faster updates
        else:
            config.max_unavailable = "25%"
            config.max_surge = "25%"


class NFRDeployProfileMapper:
    """Haupt-Mapper für NFR zu Deploy-Profile."""
    
    def __init__(self):
        self.nfr_parser = NFRParser()
        self.deployment_mapper = DeploymentMapper()
    
    def create_deployment_from_prompt(self, prompt: str, program_type: str = "web-api") -> Tuple[NFRProfile, DeploymentConfiguration]:
        """Erstelle Deployment-Konfiguration aus Prompt."""
        
        # Parse NFRs aus Prompt
        nfr_profile = self.nfr_parser.parse_nfr_from_prompt(prompt)
        
        # Anpassungen basierend auf Programm-Typ
        self._adjust_for_program_type(nfr_profile, program_type)
        
        # Mappe zu Deployment-Konfiguration
        deployment_config = self.deployment_mapper.map_nfr_to_deployment(nfr_profile)
        
        logger.info(f"Created deployment config from prompt: {nfr_profile.latency_class.value} latency, {nfr_profile.throughput_class.value} throughput")
        
        return nfr_profile, deployment_config
    
    def _adjust_for_program_type(self, nfr_profile: NFRProfile, program_type: str):
        """Passe NFR-Profile für Programm-Typ an."""
        
        if program_type == "cli":
            # CLI tools don't need high availability
            nfr_profile.availability_class = AvailabilityClass.DEVELOPMENT
            nfr_profile.min_instances = 1
            nfr_profile.max_instances = 1
            nfr_profile.startup_time_max_seconds = 10
        
        elif program_type == "worker":
            # Workers can tolerate higher latency but need throughput
            if nfr_profile.latency_class == LatencyClass.ULTRA_LOW:
                nfr_profile.latency_class = LatencyClass.LOW
            nfr_profile.startup_time_max_seconds = 60
        
        elif program_type == "batch":
            # Batch jobs prioritize throughput over latency
            nfr_profile.latency_class = LatencyClass.RELAXED
            nfr_profile.max_response_time_ms = 10000
            nfr_profile.startup_time_max_seconds = 120
        
        # web-api keeps defaults
    
    def compare_deployment_configs(self, config1: DeploymentConfiguration, config2: DeploymentConfiguration) -> Dict[str, Any]:
        """Vergleiche zwei Deployment-Konfigurationen."""
        
        differences = {}
        config1_dict = config1.to_dict()
        config2_dict = config2.to_dict()
        
        for key in config1_dict:
            if config1_dict[key] != config2_dict[key]:
                differences[key] = {
                    "config1": config1_dict[key],
                    "config2": config2_dict[key],
                    "change": self._describe_change(key, config1_dict[key], config2_dict[key])
                }
        
        return differences
    
    def _describe_change(self, key: str, old_value: Any, new_value: Any) -> str:
        """Beschreibe Änderung zwischen Werten."""
        
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            if new_value > old_value:
                return f"increased from {old_value} to {new_value}"
            else:
                return f"decreased from {old_value} to {new_value}"
        
        elif isinstance(old_value, str) and old_value.endswith(('m', 'Mi', '%')):
            return f"changed from {old_value} to {new_value}"
        
        else:
            return f"changed from {old_value} to {new_value}"
    
    def generate_deployment_manifest(self, config: DeploymentConfiguration, app_name: str = "generated-app") -> str:
        """Generiere Kubernetes Deployment Manifest."""
        
        manifest = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app_name}
  labels:
    app: {app_name}
spec:
  replicas: {config.replicas}
  selector:
    matchLabels:
      app: {app_name}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: {config.max_unavailable}
      maxSurge: {config.max_surge}
  template:
    metadata:
      labels:
        app: {app_name}
    spec:
      containers:
      - name: {app_name}
        image: {app_name}:latest
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: {config.cpu_request}
            memory: {config.memory_request}
          limits:
            cpu: {config.cpu_limit}
            memory: {config.memory_limit}
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: {config.readiness_probe_initial_delay}
          periodSeconds: {config.readiness_probe_period}
          timeoutSeconds: {config.readiness_probe_timeout}
          failureThreshold: {config.readiness_probe_failure_threshold}
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: {config.liveness_probe_initial_delay}
          periodSeconds: {config.liveness_probe_period}
          timeoutSeconds: {config.liveness_probe_timeout}
          failureThreshold: {config.liveness_probe_failure_threshold}
        env:
        - name: LOGGING_LEVEL
          value: "{config.logging_level}"
        - name: METRICS_ENABLED
          value: "{str(config.metrics_enabled).lower()}"
        - name: TRACE_SAMPLING_RATE
          value: "{config.trace_sampling_rate}"
---
apiVersion: v1
kind: Service
metadata:
  name: {app_name}-service
spec:
  selector:
    app: {app_name}
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: ClusterIP
  sessionAffinity: {"ClientIP" if config.session_affinity else "None"}
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {app_name}-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {app_name}
  minReplicas: {config.min_replicas}
  maxReplicas: {config.max_replicas}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {config.target_cpu_utilization}
        """
        
        return manifest.strip()


# Convenience Functions
def create_nfr_deploy_mapper() -> NFRDeployProfileMapper:
    """
    Erstelle NFR-Deploy-Profile-Mapper.
    
    Returns:
        NFR-Deploy-Profile-Mapper
    """
    
    return NFRDeployProfileMapper()


def map_prompt_to_deployment(
    mapper: NFRDeployProfileMapper,
    prompt: str,
    program_type: str = "web-api"
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Mappe Prompt zu Deployment-Konfiguration.
    
    Args:
        mapper: Mapper
        prompt: User-Prompt
        program_type: Programm-Typ
        
    Returns:
        (NFR Profile Dict, Deployment Config Dict)
    """
    
    nfr_profile, deployment_config = mapper.create_deployment_from_prompt(prompt, program_type)
    
    return nfr_profile.to_dict(), deployment_config.to_dict()


if __name__ == "__main__":
    # Demo
    
    def demo_nfr_deploy_profile_mapper():
        print("📊 NFR Deploy Profile Mapper Demo:")
        
        # Test 1: Erstelle Mapper
        print("\\n🚀 Creating NFR deploy profile mapper:")
        
        mapper = create_nfr_deploy_mapper()
        
        print(f"  ✓ NFR parser ready with {len(mapper.nfr_parser.latency_patterns)} latency patterns")
        print(f"  ✓ Deployment mapper ready")
        
        # Test 2: Teste verschiedene Prompts mit unterschiedlichen NFRs
        print("\\n🎯 Testing different NFR prompts:")
        
        test_prompts = [
            {
                "name": "High Performance API",
                "prompt": "Create a high-performance API with low latency < 100ms and high throughput > 1000 req/s",
                "type": "web-api"
            },
            {
                "name": "Batch Processing",
                "prompt": "Build a batch processing system for large datasets with relaxed latency but high availability",
                "type": "batch"
            },
            {
                "name": "Lightweight Service",
                "prompt": "Create a lightweight microservice with minimal resources and basic availability",
                "type": "web-api"
            },
            {
                "name": "Critical System",
                "prompt": "Build a critical system with ultra low latency < 10ms and 99.99% availability",
                "type": "web-api"
            }
        ]
        
        configs = []
        
        for test in test_prompts:
            print(f"\\n  📝 {test['name']}:")
            print(f"     Prompt: {test['prompt']}")
            
            nfr_profile, deployment_config = mapper.create_deployment_from_prompt(test['prompt'], test['type'])
            configs.append((test['name'], nfr_profile, deployment_config))
            
            print(f"     ✓ Latency class: {nfr_profile.latency_class.value}")
            print(f"     ✓ Throughput class: {nfr_profile.throughput_class.value}")
            print(f"     ✓ Availability class: {nfr_profile.availability_class.value}")
            print(f"     ✓ CPU limit: {deployment_config.cpu_limit}")
            print(f"     ✓ Memory limit: {deployment_config.memory_limit}")
            print(f"     ✓ Replicas: {deployment_config.replicas}")
            print(f"     ✓ Readiness probe period: {deployment_config.readiness_probe_period}s")
        
        # Test 3: Vergleiche Deployment-Konfigurationen
        print("\\n🔍 Comparing deployment configurations:")
        
        high_perf_config = configs[0][2]  # High Performance API
        lightweight_config = configs[2][2]  # Lightweight Service
        
        differences = mapper.compare_deployment_configs(lightweight_config, high_perf_config)
        
        print(f"  ✓ Found {len(differences)} differences between Lightweight and High Performance:")
        
        for key, diff in list(differences.items())[:5]:  # Erste 5
            print(f"    • {key}: {diff['change']}")
        
        # Test 4: Generiere Kubernetes Manifest
        print("\\n📄 Generating Kubernetes manifest:")
        
        critical_config = configs[3][2]  # Critical System
        manifest = mapper.generate_deployment_manifest(critical_config, "critical-app")
        
        manifest_lines = manifest.split('\\n')
        print(f"  ✓ Generated manifest with {len(manifest_lines)} lines")
        print(f"  ✓ Preview (first 10 lines):")
        
        for line in manifest_lines[:10]:
            if line.strip():
                print(f"    {line}")
        
        # Test 5: Teste spezifische NFR-Extraktion
        print("\\n🔍 Testing specific NFR extraction:")
        
        specific_prompt = "Create an API with 50ms response time, 500 req/s throughput, 2 CPU cores, 1GB memory"
        nfr_profile, deployment_config = mapper.create_deployment_from_prompt(specific_prompt)
        
        print(f"  ✓ Extracted max response time: {nfr_profile.max_response_time_ms}ms")
        print(f"  ✓ Extracted target RPS: {nfr_profile.target_rps}")
        print(f"  ✓ Extracted CPU cores: {nfr_profile.cpu_cores}")
        print(f"  ✓ Extracted memory: {nfr_profile.memory_mb}MB")
        print(f"  ✓ Mapped to CPU limit: {deployment_config.cpu_limit}")
        print(f"  ✓ Mapped to memory limit: {deployment_config.memory_limit}")
        
        # Test 6: Teste messbare E2E-Unterschiede
        print("\\n📊 Testing measurable E2E differences:")
        
        # Baseline vs High Performance
        baseline_prompt = "Create a standard web API"
        high_perf_prompt = "Create a high-performance API with low latency and high throughput"
        
        baseline_nfr, baseline_config = mapper.create_deployment_from_prompt(baseline_prompt)
        high_perf_nfr, high_perf_config = mapper.create_deployment_from_prompt(high_perf_prompt)
        
        e2e_differences = mapper.compare_deployment_configs(baseline_config, high_perf_config)
        
        print(f"  ✓ Baseline vs High Performance differences: {len(e2e_differences)}")
        
        # Messbare Unterschiede
        measurable_changes = []
        
        for key, diff in e2e_differences.items():
            if key in ['readiness_probe_period', 'liveness_probe_period', 'service_timeout_seconds', 'replicas', 'cpu_limit', 'memory_limit']:
                measurable_changes.append(f"{key}: {diff['change']}")
        
        print(f"  ✓ Measurable E2E changes: {len(measurable_changes)}")
        
        for change in measurable_changes[:3]:  # Erste 3
            print(f"    • {change}")
        
        # Test Akzeptanz-Kriterien
        print("\\n🎯 Acceptance criteria:")
        
        # Interpretiere Latenz- und Durchsatzklassen
        latency_classes_interpreted = len(set(config[1].latency_class for _, config in [(name, nfr, deploy) for name, nfr, deploy in configs])) > 1
        throughput_classes_interpreted = len(set(config[1].throughput_class for _, config in [(name, nfr, deploy) for name, nfr, deploy in configs])) > 1
        
        # Setze Timeouts, Concurrency, Probe-Intervalle
        timeouts_configured = any(
            config[2].service_timeout_seconds != 30 or 
            config[2].readiness_probe_period != 10 
            for _, config in [(name, nfr, deploy) for name, nfr, deploy in configs]
        )
        
        # Geänderte NFRs führen zu veränderten Deploy-Parametern
        nfr_changes_affect_deployment = len(e2e_differences) > 0
        
        # Messbare E2E-Unterschiede
        measurable_e2e_differences = len(measurable_changes) > 0
        
        print(f"  ✓ Interpretiere Latenz- und Durchsatzklassen: {latency_classes_interpreted}")
        print(f"  ✓ Interpretiere verschiedene Throughput-Klassen: {throughput_classes_interpreted}")
        print(f"  ✓ Setze Timeouts, Concurrency, Probe-Intervalle: {timeouts_configured}")
        print(f"  ✓ Geänderte NFRs führen zu veränderten Deploy-Parametern: {nfr_changes_affect_deployment}")
        print(f"  ✓ Messbare E2E-Unterschiede: {measurable_e2e_differences}")
        
        return (latency_classes_interpreted and throughput_classes_interpreted and 
               timeouts_configured and nfr_changes_affect_deployment and measurable_e2e_differences)
    
    # Führe Demo aus
    try:
        result = demo_nfr_deploy_profile_mapper()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
