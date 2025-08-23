"""
Non-Functional-Requirements abbilden.

Erweitert den Planner, um einfache NFRs zu interpretieren: 
Latenzklasse, Durchsatzklasse, Speicherobergrenze. 
Lässt diese NFRs die Default-Konfiguration und Probes beeinflussen.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

from .template_catalog import ProgramTemplate, ProgramType


logger = logging.getLogger(__name__)


class LatencyClass(Enum):
    """Latenz-Klassen."""
    ULTRA_LOW = "ultra_low"    # < 1ms
    LOW = "low"                # < 10ms
    NORMAL = "normal"          # < 100ms
    HIGH = "high"              # < 1000ms
    BATCH = "batch"            # > 1000ms


class ThroughputClass(Enum):
    """Durchsatz-Klassen."""
    ULTRA_HIGH = "ultra_high"  # > 10k req/s
    HIGH = "high"              # > 1k req/s
    NORMAL = "normal"          # > 100 req/s
    LOW = "low"                # > 10 req/s
    MINIMAL = "minimal"        # < 10 req/s


class MemoryClass(Enum):
    """Speicher-Klassen."""
    MINIMAL = "minimal"        # < 64MB
    LOW = "low"                # < 256MB
    NORMAL = "normal"          # < 512MB
    HIGH = "high"              # < 1GB
    ULTRA_HIGH = "ultra_high"  # > 1GB


@dataclass
class NonFunctionalRequirement:
    """Non-Functional Requirement."""
    
    # NFR-Typ und Wert
    requirement_type: str  # latency, throughput, memory, availability, etc.
    value: Union[int, float, str]
    unit: str
    
    # Klassifikation
    classification: Optional[Union[LatencyClass, ThroughputClass, MemoryClass]] = None
    
    # Beschreibung
    description: str = ""
    priority: str = "medium"  # low, medium, high, critical
    
    # Quelle
    source: str = "user_prompt"  # user_prompt, template_default, policy
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "requirement_type": self.requirement_type,
            "value": self.value,
            "unit": self.unit,
            "classification": self.classification.value if self.classification else None,
            "description": self.description,
            "priority": self.priority,
            "source": self.source
        }


@dataclass
class NFRProfile:
    """NFR-Profil."""
    
    # Profil-Metadaten
    profile_name: str
    template_type: ProgramType
    
    # NFR-Liste
    requirements: List[NonFunctionalRequirement] = field(default_factory=list)
    
    # Konfiguration-Anpassungen
    config_adjustments: Dict[str, Any] = field(default_factory=dict)
    
    # Probe-Anpassungen
    probe_adjustments: Dict[str, Any] = field(default_factory=dict)
    
    # Metadaten
    created_at: str = ""
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "profile_name": self.profile_name,
            "template_type": self.template_type.value,
            "requirements": [req.to_dict() for req in self.requirements],
            "config_adjustments": self.config_adjustments,
            "probe_adjustments": self.probe_adjustments,
            "created_at": self.created_at,
            "version": self.version
        }


@dataclass
class NFRImpact:
    """NFR-Auswirkung."""
    
    # Betroffene Komponente
    component: str
    parameter: str
    
    # Änderung
    original_value: Any
    new_value: Any
    
    # Begründung
    reasoning: str
    nfr_source: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "component": self.component,
            "parameter": self.parameter,
            "original_value": self.original_value,
            "new_value": self.new_value,
            "reasoning": self.reasoning,
            "nfr_source": self.nfr_source
        }


class NFRExtractor:
    """NFR-Extraktor."""
    
    def __init__(self):
        self.patterns = self._load_nfr_patterns()
    
    def extract_nfrs_from_prompt(self, prompt: str) -> List[NonFunctionalRequirement]:
        """Extrahiere NFRs aus Benutzer-Prompt."""
        logger.info("Extracting NFRs from user prompt")
        
        nfrs = []
        prompt_lower = prompt.lower()
        
        # Latenz-NFRs
        latency_nfrs = self._extract_latency_requirements(prompt_lower)
        nfrs.extend(latency_nfrs)
        
        # Durchsatz-NFRs
        throughput_nfrs = self._extract_throughput_requirements(prompt_lower)
        nfrs.extend(throughput_nfrs)
        
        # Speicher-NFRs
        memory_nfrs = self._extract_memory_requirements(prompt_lower)
        nfrs.extend(memory_nfrs)
        
        # Verfügbarkeits-NFRs
        availability_nfrs = self._extract_availability_requirements(prompt_lower)
        nfrs.extend(availability_nfrs)
        
        logger.info(f"Extracted {len(nfrs)} NFRs from prompt")
        return nfrs
    
    def _extract_latency_requirements(self, prompt: str) -> List[NonFunctionalRequirement]:
        """Extrahiere Latenz-Anforderungen."""
        nfrs = []
        
        # Patterns für Latenz
        latency_patterns = [
            (r'response time.*?(\d+)\s*(ms|milliseconds?)', 'ms'),
            (r'latency.*?(\d+)\s*(ms|milliseconds?)', 'ms'),
            (r'under (\d+)\s*(ms|milliseconds?)', 'ms'),
            (r'within (\d+)\s*(ms|milliseconds?)', 'ms'),
            (r'real.?time', 1, 'ms'),  # Real-time impliziert < 1ms
            (r'low.?latency', 10, 'ms'),  # Low-latency impliziert < 10ms
            (r'high.?performance', 50, 'ms')  # High-performance impliziert < 50ms
        ]
        
        for pattern in latency_patterns:
            if isinstance(pattern, tuple) and len(pattern) == 2:
                # Pattern mit festen Werten
                regex, value, unit = pattern[0], pattern[1], pattern[2] if len(pattern) > 2 else 'ms'
                if re.search(regex, prompt):
                    nfr = NonFunctionalRequirement(
                        requirement_type="latency",
                        value=value,
                        unit=unit,
                        description=f"Inferred from '{regex}' pattern",
                        source="user_prompt"
                    )
                    nfr.classification = self._classify_latency(value, unit)
                    nfrs.append(nfr)
            else:
                # Pattern mit extrahierten Werten
                regex, unit = pattern
                matches = re.finditer(regex, prompt)
                for match in matches:
                    value = int(match.group(1))
                    nfr = NonFunctionalRequirement(
                        requirement_type="latency",
                        value=value,
                        unit=unit,
                        description=f"Extracted from prompt: {match.group(0)}",
                        source="user_prompt"
                    )
                    nfr.classification = self._classify_latency(value, unit)
                    nfrs.append(nfr)
        
        return nfrs
    
    def _extract_throughput_requirements(self, prompt: str) -> List[NonFunctionalRequirement]:
        """Extrahiere Durchsatz-Anforderungen."""
        nfrs = []
        
        # Patterns für Durchsatz
        throughput_patterns = [
            (r'(\d+)\s*(requests?|req).*?per.*?(second|sec)', 'req/s'),
            (r'(\d+)\s*rps', 'req/s'),
            (r'(\d+)\s*qps', 'req/s'),
            (r'handle (\d+).*?users?', 'concurrent_users'),
            (r'(\d+).*?concurrent.*?users?', 'concurrent_users'),
            (r'high.*?traffic', 1000, 'req/s'),
            (r'heavy.*?load', 500, 'req/s'),
            (r'scale.*?(\d+)', 'req/s')
        ]
        
        for pattern in throughput_patterns:
            if isinstance(pattern, tuple) and len(pattern) == 3 and isinstance(pattern[1], (int, float)):
                # Pattern mit festen Werten
                regex, value, unit = pattern
                if re.search(regex, prompt):
                    nfr = NonFunctionalRequirement(
                        requirement_type="throughput",
                        value=value,
                        unit=unit,
                        description=f"Inferred from '{regex}' pattern",
                        source="user_prompt"
                    )
                    nfr.classification = self._classify_throughput(value, unit)
                    nfrs.append(nfr)
            else:
                # Pattern mit extrahierten Werten
                regex, unit = pattern
                matches = re.finditer(regex, prompt)
                for match in matches:
                    value = int(match.group(1))
                    nfr = NonFunctionalRequirement(
                        requirement_type="throughput",
                        value=value,
                        unit=unit,
                        description=f"Extracted from prompt: {match.group(0)}",
                        source="user_prompt"
                    )
                    nfr.classification = self._classify_throughput(value, unit)
                    nfrs.append(nfr)
        
        return nfrs
    
    def _extract_memory_requirements(self, prompt: str) -> List[NonFunctionalRequirement]:
        """Extrahiere Speicher-Anforderungen."""
        nfrs = []
        
        # Patterns für Speicher
        memory_patterns = [
            (r'(\d+)\s*(mb|megabytes?)', 'MB'),
            (r'(\d+)\s*(gb|gigabytes?)', 'GB'),
            (r'memory.*?(\d+)\s*(mb|gb)', None),
            (r'ram.*?(\d+)\s*(mb|gb)', None),
            (r'low.*?memory', 128, 'MB'),
            (r'minimal.*?footprint', 64, 'MB'),
            (r'lightweight', 256, 'MB')
        ]
        
        for pattern in memory_patterns:
            if isinstance(pattern, tuple) and len(pattern) == 3 and isinstance(pattern[1], (int, float)):
                # Pattern mit festen Werten
                regex, value, unit = pattern
                if re.search(regex, prompt):
                    nfr = NonFunctionalRequirement(
                        requirement_type="memory",
                        value=value,
                        unit=unit,
                        description=f"Inferred from '{regex}' pattern",
                        source="user_prompt"
                    )
                    nfr.classification = self._classify_memory(value, unit)
                    nfrs.append(nfr)
            else:
                # Pattern mit extrahierten Werten
                regex, unit_hint = pattern
                matches = re.finditer(regex, prompt)
                for match in matches:
                    value = int(match.group(1))
                    unit = match.group(2).upper() if len(match.groups()) > 1 else unit_hint
                    if unit:
                        unit = unit.replace('MEGABYTES', 'MB').replace('GIGABYTES', 'GB')
                        nfr = NonFunctionalRequirement(
                            requirement_type="memory",
                            value=value,
                            unit=unit,
                            description=f"Extracted from prompt: {match.group(0)}",
                            source="user_prompt"
                        )
                        nfr.classification = self._classify_memory(value, unit)
                        nfrs.append(nfr)
        
        return nfrs
    
    def _extract_availability_requirements(self, prompt: str) -> List[NonFunctionalRequirement]:
        """Extrahiere Verfügbarkeits-Anforderungen."""
        nfrs = []
        
        # Patterns für Verfügbarkeit
        availability_patterns = [
            (r'(\d+(?:\.\d+)?)\s*%.*?uptime', '%'),
            (r'(\d+(?:\.\d+)?)\s*%.*?availability', '%'),
            (r'99\.9.*?%', 99.9, '%'),
            (r'high.*?availability', 99.5, '%'),
            (r'24/7', 99.9, '%'),
            (r'always.*?available', 99.5, '%')
        ]
        
        for pattern in availability_patterns:
            if isinstance(pattern, tuple) and len(pattern) == 3 and isinstance(pattern[1], (int, float)):
                # Pattern mit festen Werten
                regex, value, unit = pattern
                if re.search(regex, prompt):
                    nfr = NonFunctionalRequirement(
                        requirement_type="availability",
                        value=value,
                        unit=unit,
                        description=f"Inferred from '{regex}' pattern",
                        source="user_prompt"
                    )
                    nfrs.append(nfr)
            else:
                # Pattern mit extrahierten Werten
                regex, unit = pattern
                matches = re.finditer(regex, prompt)
                for match in matches:
                    value = float(match.group(1))
                    nfr = NonFunctionalRequirement(
                        requirement_type="availability",
                        value=value,
                        unit=unit,
                        description=f"Extracted from prompt: {match.group(0)}",
                        source="user_prompt"
                    )
                    nfrs.append(nfr)
        
        return nfrs
    
    def _classify_latency(self, value: Union[int, float], unit: str) -> LatencyClass:
        """Klassifiziere Latenz."""
        # Normalisiere auf ms
        if unit.lower() in ['s', 'seconds', 'second']:
            value_ms = value * 1000
        else:
            value_ms = value
        
        if value_ms < 1:
            return LatencyClass.ULTRA_LOW
        elif value_ms < 10:
            return LatencyClass.LOW
        elif value_ms < 100:
            return LatencyClass.NORMAL
        elif value_ms < 1000:
            return LatencyClass.HIGH
        else:
            return LatencyClass.BATCH
    
    def _classify_throughput(self, value: Union[int, float], unit: str) -> ThroughputClass:
        """Klassifiziere Durchsatz."""
        # Normalisiere auf req/s
        if unit == 'concurrent_users':
            # Schätze req/s basierend auf concurrent users (Faktor 0.1)
            value_rps = value * 0.1
        else:
            value_rps = value
        
        if value_rps > 10000:
            return ThroughputClass.ULTRA_HIGH
        elif value_rps > 1000:
            return ThroughputClass.HIGH
        elif value_rps > 100:
            return ThroughputClass.NORMAL
        elif value_rps > 10:
            return ThroughputClass.LOW
        else:
            return ThroughputClass.MINIMAL
    
    def _classify_memory(self, value: Union[int, float], unit: str) -> MemoryClass:
        """Klassifiziere Speicher."""
        # Normalisiere auf MB
        if unit.upper() == 'GB':
            value_mb = value * 1024
        else:
            value_mb = value
        
        if value_mb < 64:
            return MemoryClass.MINIMAL
        elif value_mb < 256:
            return MemoryClass.LOW
        elif value_mb < 512:
            return MemoryClass.NORMAL
        elif value_mb < 1024:
            return MemoryClass.HIGH
        else:
            return MemoryClass.ULTRA_HIGH
    
    def _load_nfr_patterns(self) -> Dict[str, Any]:
        """Lade NFR-Patterns."""
        # In Produktion: aus Konfigurationsdatei laden
        return {
            "latency_keywords": ["response time", "latency", "real-time", "low-latency"],
            "throughput_keywords": ["requests per second", "rps", "qps", "concurrent users"],
            "memory_keywords": ["memory", "ram", "footprint", "lightweight"],
            "availability_keywords": ["uptime", "availability", "24/7", "high availability"]
        }


class NFRConfigurationAdapter:
    """NFR-Konfigurations-Adapter."""
    
    def __init__(self):
        self.default_configs = self._load_default_configs()
    
    def adapt_configuration(
        self,
        base_config: Dict[str, Any],
        nfrs: List[NonFunctionalRequirement],
        template_type: ProgramType
    ) -> Tuple[Dict[str, Any], List[NFRImpact]]:
        """Passe Konfiguration basierend auf NFRs an."""
        logger.info(f"Adapting configuration for {len(nfrs)} NFRs")
        
        adapted_config = base_config.copy()
        impacts = []
        
        for nfr in nfrs:
            nfr_impacts = self._apply_nfr_to_config(adapted_config, nfr, template_type)
            impacts.extend(nfr_impacts)
        
        logger.info(f"Applied {len(impacts)} configuration changes")
        return adapted_config, impacts
    
    def _apply_nfr_to_config(
        self,
        config: Dict[str, Any],
        nfr: NonFunctionalRequirement,
        template_type: ProgramType
    ) -> List[NFRImpact]:
        """Wende einzelne NFR auf Konfiguration an."""
        impacts = []
        
        if nfr.requirement_type == "latency":
            impacts.extend(self._apply_latency_nfr(config, nfr, template_type))
        elif nfr.requirement_type == "throughput":
            impacts.extend(self._apply_throughput_nfr(config, nfr, template_type))
        elif nfr.requirement_type == "memory":
            impacts.extend(self._apply_memory_nfr(config, nfr, template_type))
        elif nfr.requirement_type == "availability":
            impacts.extend(self._apply_availability_nfr(config, nfr, template_type))
        
        return impacts
    
    def _apply_latency_nfr(
        self,
        config: Dict[str, Any],
        nfr: NonFunctionalRequirement,
        template_type: ProgramType
    ) -> List[NFRImpact]:
        """Wende Latenz-NFR an."""
        impacts = []
        
        if nfr.classification == LatencyClass.ULTRA_LOW:
            # Ultra-niedrige Latenz
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 1, 
                                  "Reduced workers for ultra-low latency", nfr.description),
                self._update_config(config, "server", "keep_alive_timeout", 30, 5,
                                  "Reduced keep-alive for ultra-low latency", nfr.description),
                self._update_config(config, "cache", "enabled", False, True,
                                  "Enable caching for ultra-low latency", nfr.description)
            ])
        
        elif nfr.classification == LatencyClass.LOW:
            # Niedrige Latenz
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 2,
                                  "Optimized workers for low latency", nfr.description),
                self._update_config(config, "cache", "ttl_seconds", 300, 60,
                                  "Reduced cache TTL for low latency", nfr.description)
            ])
        
        elif nfr.classification == LatencyClass.BATCH:
            # Batch-Verarbeitung
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 8,
                                  "Increased workers for batch processing", nfr.description),
                self._update_config(config, "server", "timeout_seconds", 30, 300,
                                  "Increased timeout for batch processing", nfr.description)
            ])
        
        return impacts
    
    def _apply_throughput_nfr(
        self,
        config: Dict[str, Any],
        nfr: NonFunctionalRequirement,
        template_type: ProgramType
    ) -> List[NFRImpact]:
        """Wende Durchsatz-NFR an."""
        impacts = []
        
        if nfr.classification == ThroughputClass.ULTRA_HIGH:
            # Ultra-hoher Durchsatz
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 16,
                                  "Increased workers for ultra-high throughput", nfr.description),
                self._update_config(config, "server", "max_connections", 1000, 10000,
                                  "Increased connections for ultra-high throughput", nfr.description),
                self._update_config(config, "cache", "enabled", False, True,
                                  "Enable caching for ultra-high throughput", nfr.description)
            ])
        
        elif nfr.classification == ThroughputClass.HIGH:
            # Hoher Durchsatz
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 8,
                                  "Increased workers for high throughput", nfr.description),
                self._update_config(config, "server", "max_connections", 1000, 5000,
                                  "Increased connections for high throughput", nfr.description)
            ])
        
        elif nfr.classification == ThroughputClass.MINIMAL:
            # Minimaler Durchsatz
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 1,
                                  "Reduced workers for minimal throughput", nfr.description),
                self._update_config(config, "server", "max_connections", 1000, 100,
                                  "Reduced connections for minimal throughput", nfr.description)
            ])
        
        return impacts
    
    def _apply_memory_nfr(
        self,
        config: Dict[str, Any],
        nfr: NonFunctionalRequirement,
        template_type: ProgramType
    ) -> List[NFRImpact]:
        """Wende Speicher-NFR an."""
        impacts = []
        
        if nfr.classification == MemoryClass.MINIMAL:
            # Minimaler Speicher
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 1,
                                  "Reduced workers for minimal memory", nfr.description),
                self._update_config(config, "cache", "max_size_mb", 100, 32,
                                  "Reduced cache size for minimal memory", nfr.description),
                self._update_config(config, "logging", "buffer_size", 1000, 100,
                                  "Reduced logging buffer for minimal memory", nfr.description)
            ])
        
        elif nfr.classification == MemoryClass.LOW:
            # Niedriger Speicher
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 2,
                                  "Reduced workers for low memory", nfr.description),
                self._update_config(config, "cache", "max_size_mb", 100, 64,
                                  "Reduced cache size for low memory", nfr.description)
            ])
        
        elif nfr.classification == MemoryClass.ULTRA_HIGH:
            # Ultra-hoher Speicher
            impacts.extend([
                self._update_config(config, "server", "worker_processes", 4, 16,
                                  "Increased workers for ultra-high memory", nfr.description),
                self._update_config(config, "cache", "max_size_mb", 100, 1024,
                                  "Increased cache size for ultra-high memory", nfr.description)
            ])
        
        return impacts
    
    def _apply_availability_nfr(
        self,
        config: Dict[str, Any],
        nfr: NonFunctionalRequirement,
        template_type: ProgramType
    ) -> List[NFRImpact]:
        """Wende Verfügbarkeits-NFR an."""
        impacts = []
        
        if nfr.value >= 99.9:  # High availability
            impacts.extend([
                self._update_config(config, "health_check", "enabled", False, True,
                                  "Enable health checks for high availability", nfr.description),
                self._update_config(config, "health_check", "interval_seconds", 30, 10,
                                  "Increased health check frequency for high availability", nfr.description),
                self._update_config(config, "server", "graceful_shutdown_timeout", 10, 30,
                                  "Increased graceful shutdown for high availability", nfr.description)
            ])
        
        return impacts
    
    def _update_config(
        self,
        config: Dict[str, Any],
        section: str,
        key: str,
        original_value: Any,
        new_value: Any,
        reasoning: str,
        nfr_source: str
    ) -> NFRImpact:
        """Update Konfiguration und erstelle Impact."""
        # Erstelle Section falls nicht vorhanden
        if section not in config:
            config[section] = {}
        
        # Hole aktuellen Wert
        current_value = config[section].get(key, original_value)
        
        # Setze neuen Wert
        config[section][key] = new_value
        
        return NFRImpact(
            component=section,
            parameter=key,
            original_value=current_value,
            new_value=new_value,
            reasoning=reasoning,
            nfr_source=nfr_source
        )
    
    def _load_default_configs(self) -> Dict[str, Any]:
        """Lade Standard-Konfigurationen."""
        return {
            "server": {
                "worker_processes": 4,
                "max_connections": 1000,
                "keep_alive_timeout": 30,
                "timeout_seconds": 30,
                "graceful_shutdown_timeout": 10
            },
            "cache": {
                "enabled": False,
                "max_size_mb": 100,
                "ttl_seconds": 300
            },
            "health_check": {
                "enabled": False,
                "interval_seconds": 30,
                "timeout_seconds": 5
            },
            "logging": {
                "buffer_size": 1000,
                "level": "INFO"
            }
        }


class NFRProbeAdapter:
    """NFR-Probe-Adapter."""
    
    def __init__(self):
        pass
    
    def adapt_probes(
        self,
        base_probes: Dict[str, Any],
        nfrs: List[NonFunctionalRequirement]
    ) -> Tuple[Dict[str, Any], List[NFRImpact]]:
        """Passe Probes basierend auf NFRs an."""
        logger.info(f"Adapting probes for {len(nfrs)} NFRs")
        
        adapted_probes = base_probes.copy()
        impacts = []
        
        for nfr in nfrs:
            nfr_impacts = self._apply_nfr_to_probes(adapted_probes, nfr)
            impacts.extend(nfr_impacts)
        
        logger.info(f"Applied {len(impacts)} probe changes")
        return adapted_probes, impacts
    
    def _apply_nfr_to_probes(
        self,
        probes: Dict[str, Any],
        nfr: NonFunctionalRequirement
    ) -> List[NFRImpact]:
        """Wende NFR auf Probes an."""
        impacts = []
        
        if nfr.requirement_type == "latency":
            impacts.extend(self._adapt_latency_probes(probes, nfr))
        elif nfr.requirement_type == "throughput":
            impacts.extend(self._adapt_throughput_probes(probes, nfr))
        elif nfr.requirement_type == "memory":
            impacts.extend(self._adapt_memory_probes(probes, nfr))
        elif nfr.requirement_type == "availability":
            impacts.extend(self._adapt_availability_probes(probes, nfr))
        
        return impacts
    
    def _adapt_latency_probes(
        self,
        probes: Dict[str, Any],
        nfr: NonFunctionalRequirement
    ) -> List[NFRImpact]:
        """Passe Latenz-Probes an."""
        impacts = []
        
        # Health Check Probe
        if "health_check" not in probes:
            probes["health_check"] = {}
        
        if nfr.classification in [LatencyClass.ULTRA_LOW, LatencyClass.LOW]:
            # Schnellere Health Checks für niedrige Latenz
            impacts.append(self._update_probe(
                probes, "health_check", "timeout_seconds", 5, 2,
                f"Reduced health check timeout for {nfr.classification.value} latency", nfr.description
            ))
            impacts.append(self._update_probe(
                probes, "health_check", "interval_seconds", 10, 5,
                f"Increased health check frequency for {nfr.classification.value} latency", nfr.description
            ))
        
        # Readiness Probe
        if "readiness" not in probes:
            probes["readiness"] = {}
        
        impacts.append(self._update_probe(
            probes, "readiness", "initial_delay_seconds", 10, 5,
            f"Reduced readiness delay for {nfr.classification.value} latency", nfr.description
        ))
        
        return impacts
    
    def _adapt_throughput_probes(
        self,
        probes: Dict[str, Any],
        nfr: NonFunctionalRequirement
    ) -> List[NFRImpact]:
        """Passe Durchsatz-Probes an."""
        impacts = []
        
        if nfr.classification in [ThroughputClass.ULTRA_HIGH, ThroughputClass.HIGH]:
            # Weniger aggressive Probes für hohen Durchsatz
            impacts.append(self._update_probe(
                probes, "health_check", "interval_seconds", 10, 30,
                f"Reduced health check frequency for {nfr.classification.value} throughput", nfr.description
            ))
        
        return impacts
    
    def _adapt_memory_probes(
        self,
        probes: Dict[str, Any],
        nfr: NonFunctionalRequirement
    ) -> List[NFRImpact]:
        """Passe Speicher-Probes an."""
        impacts = []
        
        if nfr.classification in [MemoryClass.MINIMAL, MemoryClass.LOW]:
            # Memory-optimierte Probes
            impacts.append(self._update_probe(
                probes, "health_check", "memory_threshold_mb", 100, int(nfr.value * 0.8),
                f"Adjusted memory threshold for {nfr.classification.value} memory", nfr.description
            ))
        
        return impacts
    
    def _adapt_availability_probes(
        self,
        probes: Dict[str, Any],
        nfr: NonFunctionalRequirement
    ) -> List[NFRImpact]:
        """Passe Verfügbarkeits-Probes an."""
        impacts = []
        
        if nfr.value >= 99.9:  # High availability
            # Robustere Probes für hohe Verfügbarkeit
            impacts.extend([
                self._update_probe(
                    probes, "health_check", "failure_threshold", 3, 1,
                    "Reduced failure threshold for high availability", nfr.description
                ),
                self._update_probe(
                    probes, "readiness", "failure_threshold", 3, 1,
                    "Reduced readiness failure threshold for high availability", nfr.description
                )
            ])
        
        return impacts
    
    def _update_probe(
        self,
        probes: Dict[str, Any],
        probe_type: str,
        key: str,
        original_value: Any,
        new_value: Any,
        reasoning: str,
        nfr_source: str
    ) -> NFRImpact:
        """Update Probe und erstelle Impact."""
        if probe_type not in probes:
            probes[probe_type] = {}
        
        current_value = probes[probe_type].get(key, original_value)
        probes[probe_type][key] = new_value
        
        return NFRImpact(
            component=f"probe_{probe_type}",
            parameter=key,
            original_value=current_value,
            new_value=new_value,
            reasoning=reasoning,
            nfr_source=nfr_source
        )


class NFRPlanner:
    """NFR-Planner."""
    
    def __init__(self):
        self.extractor = NFRExtractor()
        self.config_adapter = NFRConfigurationAdapter()
        self.probe_adapter = NFRProbeAdapter()
    
    def plan_nfr_adaptations(
        self,
        user_prompt: str,
        template: ProgramTemplate,
        base_config: Dict[str, Any],
        base_probes: Dict[str, Any]
    ) -> NFRProfile:
        """Plane NFR-Anpassungen."""
        logger.info(f"Planning NFR adaptations for template: {template.name}")
        
        # Extrahiere NFRs aus Prompt
        nfrs = self.extractor.extract_nfrs_from_prompt(user_prompt)
        
        # Erstelle NFR-Profil
        profile = NFRProfile(
            profile_name=f"{template.name}_nfr_profile",
            template_type=template.program_type,
            requirements=nfrs,
            created_at=datetime.utcnow().isoformat()
        )
        
        # Passe Konfiguration an
        adapted_config, config_impacts = self.config_adapter.adapt_configuration(
            base_config, nfrs, template.program_type
        )
        profile.config_adjustments = adapted_config
        
        # Passe Probes an
        adapted_probes, probe_impacts = self.probe_adapter.adapt_probes(
            base_probes, nfrs
        )
        profile.probe_adjustments = adapted_probes
        
        # Dokumentiere alle Impacts
        all_impacts = config_impacts + probe_impacts
        profile.config_adjustments["_nfr_impacts"] = [impact.to_dict() for impact in all_impacts]
        
        logger.info(f"Created NFR profile with {len(nfrs)} requirements and {len(all_impacts)} impacts")
        return profile
    
    def get_nfr_summary(self, profile: NFRProfile) -> Dict[str, Any]:
        """Hole NFR-Zusammenfassung."""
        summary = {
            "profile_name": profile.profile_name,
            "template_type": profile.template_type.value,
            "total_requirements": len(profile.requirements),
            "requirements_by_type": {},
            "total_impacts": len(profile.config_adjustments.get("_nfr_impacts", [])),
            "impacts_by_component": {}
        }
        
        # Gruppiere Requirements nach Typ
        for req in profile.requirements:
            req_type = req.requirement_type
            if req_type not in summary["requirements_by_type"]:
                summary["requirements_by_type"][req_type] = 0
            summary["requirements_by_type"][req_type] += 1
        
        # Gruppiere Impacts nach Komponente
        impacts = profile.config_adjustments.get("_nfr_impacts", [])
        for impact in impacts:
            component = impact["component"]
            if component not in summary["impacts_by_component"]:
                summary["impacts_by_component"][component] = 0
            summary["impacts_by_component"][component] += 1
        
        return summary


# Convenience Functions
def plan_nfr_configuration(
    user_prompt: str,
    template: ProgramTemplate,
    base_config: Optional[Dict[str, Any]] = None,
    base_probes: Optional[Dict[str, Any]] = None
) -> NFRProfile:
    """
    Convenience-Funktion für NFR-Planung.
    
    Args:
        user_prompt: Benutzer-Prompt mit NFRs
        template: Program-Template
        base_config: Basis-Konfiguration
        base_probes: Basis-Probes
        
    Returns:
        NFR-Profil mit Anpassungen
    """
    if base_config is None:
        base_config = {
            "server": {"worker_processes": 4, "max_connections": 1000},
            "cache": {"enabled": False, "max_size_mb": 100},
            "health_check": {"enabled": False, "interval_seconds": 30}
        }
    
    if base_probes is None:
        base_probes = {
            "health_check": {"timeout_seconds": 5, "interval_seconds": 10},
            "readiness": {"initial_delay_seconds": 10, "failure_threshold": 3}
        }
    
    planner = NFRPlanner()
    return planner.plan_nfr_adaptations(user_prompt, template, base_config, base_probes)


if __name__ == "__main__":
    # Demo
    from .template_catalog import get_catalog
    
    def demo_nfr_planner():
        print("📊 NFR Planner Demo:")
        
        # Hole Template
        catalog = get_catalog()
        template = catalog.get_template("python-web-api")
        
        if not template:
            print("Template not found")
            return False
        
        # Test-Prompts mit verschiedenen NFRs
        test_prompts = [
            "Create a high-performance API that responds within 50ms and handles 1000 requests per second",
            "Build a lightweight microservice with minimal memory footprint under 128MB",
            "Develop a real-time API with ultra-low latency and 99.9% uptime",
            "Create a batch processing service that can handle heavy loads with 2GB memory"
        ]
        
        planner = NFRPlanner()
        
        print(f"\\nTesting {len(test_prompts)} NFR scenarios:")
        
        for i, prompt in enumerate(test_prompts, 1):
            print(f"\\n🧪 Scenario {i}:")
            print(f"  Prompt: {prompt}")
            
            # Plane NFR-Anpassungen
            profile = plan_nfr_configuration(prompt, template)
            
            print(f"  ✓ NFR Profile: {profile.profile_name}")
            print(f"  ✓ Requirements: {len(profile.requirements)}")
            
            # Zeige extrahierte NFRs
            for req in profile.requirements:
                print(f"    - {req.requirement_type}: {req.value} {req.unit}")
                if req.classification:
                    print(f"      Classification: {req.classification.value}")
            
            # Zeige Impacts
            impacts = profile.config_adjustments.get("_nfr_impacts", [])
            print(f"  ✓ Configuration Impacts: {len(impacts)}")
            
            for impact in impacts[:3]:  # Erste 3 Impacts
                print(f"    - {impact['component']}.{impact['parameter']}: {impact['original_value']} → {impact['new_value']}")
                print(f"      Reason: {impact['reasoning']}")
            
            # Hole Summary
            summary = planner.get_nfr_summary(profile)
            print(f"  ✓ Summary:")
            print(f"    Requirements by type: {summary['requirements_by_type']}")
            print(f"    Impacts by component: {summary['impacts_by_component']}")
        
        # Teste Akzeptanz-Kriterium
        print(f"\\n🎯 Testing Acceptance Criteria:")
        
        acceptance_prompt = "Create an API with response time under 100ms and handle 500 concurrent users"
        acceptance_profile = plan_nfr_configuration(acceptance_prompt, template)
        
        # Prüfe ob NFRs zu veränderten Parametern führen
        impacts = acceptance_profile.config_adjustments.get("_nfr_impacts", [])
        parameter_changes = len(impacts) > 0
        
        # Prüfe ob Änderungen im E2E-Harness sichtbar wären
        e2e_visible_changes = any(
            impact["component"] in ["server", "health_check", "probe_health_check", "probe_readiness"]
            for impact in impacts
        )
        
        print(f"  NFRs lead to parameter changes: {parameter_changes}")
        print(f"  Changes visible in E2E harness: {e2e_visible_changes}")
        print(f"  Total parameter changes: {len(impacts)}")
        
        if impacts:
            print(f"  Example changes:")
            for impact in impacts[:2]:
                print(f"    - {impact['component']}.{impact['parameter']}: {impact['original_value']} → {impact['new_value']}")
        
        return parameter_changes and e2e_visible_changes
    
    # Führe Demo aus
    try:
        result = demo_nfr_planner()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
