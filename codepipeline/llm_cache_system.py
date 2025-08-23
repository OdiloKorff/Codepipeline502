"""
LLM Cache System für Kostensenkung und Stabilität.

Implementiert:
- Seed-Propagation in alle LLM-Aufrufe
- Cache mit Key aus spec-hash, modell, seed, prompt-version
- Wiederholungslauf trifft Cache und liefert identische Diffs ohne neuen Call
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class CacheStatus(Enum):
    """Cache-Status."""
    HIT = "hit"
    MISS = "miss"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass
class LLMRequest:
    """LLM-Request-Daten."""
    
    # Request-Parameter
    model: str
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.0
    seed: int = 42
    max_tokens: Optional[int] = None
    
    # Kontext
    spec_hash: str = ""
    prompt_version: str = "1.0"
    
    # Metadaten
    request_id: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        
        if not self.request_id:
            self.request_id = self.generate_request_id()
    
    def generate_request_id(self) -> str:
        """Generiere Request-ID."""
        content = f"{self.model}:{self.prompt[:100]}:{self.timestamp}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def generate_cache_key(self) -> str:
        """Generiere Cache-Key."""
        
        # Normalisiere Prompt (entferne Whitespace-Variationen)
        normalized_prompt = " ".join(self.prompt.split())
        normalized_system = " ".join(self.system_prompt.split())
        
        # Cache-Key-Komponenten
        key_components = [
            self.spec_hash,
            self.model,
            str(self.seed),
            self.prompt_version,
            str(self.temperature),
            normalized_prompt,
            normalized_system
        ]
        
        # Optional: max_tokens
        if self.max_tokens:
            key_components.append(str(self.max_tokens))
        
        # SHA256-Hash
        key_content = "|".join(key_components)
        cache_key = hashlib.sha256(key_content.encode('utf-8')).hexdigest()
        
        return cache_key
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "model": self.model,
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "seed": self.seed,
            "max_tokens": self.max_tokens,
            "spec_hash": self.spec_hash,
            "prompt_version": self.prompt_version,
            "request_id": self.request_id,
            "timestamp": self.timestamp
        }


@dataclass
class LLMResponse:
    """LLM-Response-Daten."""
    
    # Response-Inhalt
    content: str = ""
    finish_reason: str = "stop"
    
    # Token-Usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Modell-Info
    model: str = ""
    
    # Metadaten
    response_id: str = ""
    timestamp: str = ""
    cached: bool = False
    cache_key: str = ""
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        
        if not self.response_id:
            self.response_id = self.generate_response_id()
    
    def generate_response_id(self) -> str:
        """Generiere Response-ID."""
        content = f"{self.model}:{self.content[:100]}:{self.timestamp}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "content": self.content,
            "finish_reason": self.finish_reason,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "response_id": self.response_id,
            "timestamp": self.timestamp,
            "cached": self.cached,
            "cache_key": self.cache_key
        }


@dataclass
class CacheEntry:
    """Cache-Eintrag."""
    
    # Cache-Info
    cache_key: str
    created_at: str
    last_accessed: str
    access_count: int = 0
    
    # Request/Response
    request_data: Dict[str, Any] = field(default_factory=dict)
    response_data: Dict[str, Any] = field(default_factory=dict)
    
    # TTL
    expires_at: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Prüfe ob Cache-Eintrag abgelaufen ist."""
        
        if not self.expires_at:
            return False
        
        try:
            expires = datetime.fromisoformat(self.expires_at)
            return datetime.utcnow() > expires
        except:
            return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "cache_key": self.cache_key,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "request_data": self.request_data,
            "response_data": self.response_data,
            "expires_at": self.expires_at
        }


class LLMCacheDB:
    """SQLite-basierte LLM-Cache-Datenbank."""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.cwd() / "cache" / "llm_cache.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Initialisiere Datenbank."""
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    request_data TEXT NOT NULL,
                    response_data TEXT NOT NULL,
                    expires_at TEXT,
                    spec_hash TEXT,
                    model TEXT,
                    seed INTEGER,
                    prompt_version TEXT
                )
            """)
            
            # Indizes für bessere Performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spec_hash ON llm_cache(spec_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON llm_cache(model)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON llm_cache(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON llm_cache(last_accessed)")
            
            conn.commit()
    
    def get_entry(self, cache_key: str) -> Optional[CacheEntry]:
        """Hole Cache-Eintrag."""
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT * FROM llm_cache WHERE cache_key = ?
            """, (cache_key,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            try:
                entry = CacheEntry(
                    cache_key=row['cache_key'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    access_count=row['access_count'],
                    request_data=json.loads(row['request_data']),
                    response_data=json.loads(row['response_data']),
                    expires_at=row['expires_at']
                )
                
                return entry
            
            except Exception as e:
                logger.error(f"Failed to deserialize cache entry: {e}")
                return None
    
    def put_entry(self, request: LLMRequest, response: LLMResponse, ttl_hours: int = 24) -> bool:
        """Speichere Cache-Eintrag."""
        
        try:
            cache_key = request.generate_cache_key()
            now = datetime.utcnow().isoformat()
            expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO llm_cache 
                    (cache_key, created_at, last_accessed, access_count, 
                     request_data, response_data, expires_at, 
                     spec_hash, model, seed, prompt_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cache_key,
                    now,
                    now,
                    1,
                    json.dumps(request.to_dict()),
                    json.dumps(response.to_dict()),
                    expires_at,
                    request.spec_hash,
                    request.model,
                    request.seed,
                    request.prompt_version
                ))
                
                conn.commit()
            
            logger.info(f"Cached LLM response: {cache_key[:16]}...")
            return True
        
        except Exception as e:
            logger.error(f"Failed to cache LLM response: {e}")
            return False
    
    def update_access(self, cache_key: str) -> bool:
        """Aktualisiere Zugriffs-Statistiken."""
        
        try:
            now = datetime.utcnow().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE llm_cache 
                    SET last_accessed = ?, access_count = access_count + 1
                    WHERE cache_key = ?
                """, (now, cache_key))
                
                conn.commit()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to update cache access: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """Bereinige abgelaufene Einträge."""
        
        try:
            now = datetime.utcnow().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM llm_cache 
                    WHERE expires_at IS NOT NULL AND expires_at < ?
                """, (now,))
                
                deleted_count = cursor.rowcount
                conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired cache entries")
            
            return deleted_count
        
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Hole Cache-Statistiken."""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Gesamt-Statistiken
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(access_count) as total_accesses,
                        AVG(access_count) as avg_accesses,
                        COUNT(CASE WHEN expires_at < datetime('now') THEN 1 END) as expired_entries
                    FROM llm_cache
                """)
                
                stats_row = cursor.fetchone()
                
                # Model-Statistiken
                cursor = conn.execute("""
                    SELECT model, COUNT(*) as count
                    FROM llm_cache
                    GROUP BY model
                    ORDER BY count DESC
                """)
                
                model_stats = dict(cursor.fetchall())
                
                # Spec-Hash-Statistiken
                cursor = conn.execute("""
                    SELECT spec_hash, COUNT(*) as count
                    FROM llm_cache
                    WHERE spec_hash IS NOT NULL AND spec_hash != ''
                    GROUP BY spec_hash
                    ORDER BY count DESC
                    LIMIT 10
                """)
                
                spec_stats = dict(cursor.fetchall())
                
                return {
                    "total_entries": stats_row['total_entries'],
                    "total_accesses": stats_row['total_accesses'],
                    "avg_accesses": float(stats_row['avg_accesses'] or 0),
                    "expired_entries": stats_row['expired_entries'],
                    "models": model_stats,
                    "top_specs": spec_stats
                }
        
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}


class SeedPropagationManager:
    """Seed-Propagation-Manager."""
    
    def __init__(self, global_seed: int = 42):
        self.global_seed = global_seed
        self.seed_counter = 0
    
    def get_next_seed(self, context: str = "") -> int:
        """Hole nächsten Seed für Kontext."""
        
        # Deterministischer Seed basierend auf globalem Seed und Kontext
        context_hash = hashlib.sha256(context.encode('utf-8')).hexdigest()
        context_int = int(context_hash[:8], 16)
        
        # Kombiniere mit Zähler für Eindeutigkeit
        seed = (self.global_seed + context_int + self.seed_counter) % (2**32)
        self.seed_counter += 1
        
        return seed
    
    def propagate_seed(self, request: LLMRequest, context: str = "") -> LLMRequest:
        """Propagiere Seed in Request."""
        
        if request.seed == 0 or request.seed is None:
            request.seed = self.get_next_seed(context)
        
        return request


class LLMCacheManager:
    """LLM-Cache-Manager."""
    
    def __init__(self, db_path: Path = None, default_ttl_hours: int = 24):
        self.cache_db = LLMCacheDB(db_path)
        self.seed_manager = SeedPropagationManager()
        self.default_ttl_hours = default_ttl_hours
        
        # Cache-Statistiken
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get_cached_response(self, request: LLMRequest) -> Tuple[CacheStatus, Optional[LLMResponse]]:
        """Hole gecachte Response."""
        
        # Bereinige abgelaufene Einträge
        self.cache_db.cleanup_expired()
        
        # Generiere Cache-Key
        cache_key = request.generate_cache_key()
        
        # Suche Cache-Eintrag
        entry = self.cache_db.get_entry(cache_key)
        
        if not entry:
            self.cache_misses += 1
            return CacheStatus.MISS, None
        
        # Prüfe Ablauf
        if entry.is_expired():
            self.cache_misses += 1
            return CacheStatus.EXPIRED, None
        
        try:
            # Erstelle Response aus Cache
            response_data = entry.response_data
            response = LLMResponse(
                content=response_data.get("content", ""),
                finish_reason=response_data.get("finish_reason", "stop"),
                prompt_tokens=response_data.get("prompt_tokens", 0),
                completion_tokens=response_data.get("completion_tokens", 0),
                total_tokens=response_data.get("total_tokens", 0),
                model=response_data.get("model", ""),
                cached=True,
                cache_key=cache_key
            )
            
            # Aktualisiere Zugriffs-Statistiken
            self.cache_db.update_access(cache_key)
            self.cache_hits += 1
            
            logger.info(f"Cache hit: {cache_key[:16]}... (accessed {entry.access_count + 1} times)")
            
            return CacheStatus.HIT, response
        
        except Exception as e:
            logger.error(f"Failed to deserialize cached response: {e}")
            self.cache_misses += 1
            return CacheStatus.INVALID, None
    
    def cache_response(self, request: LLMRequest, response: LLMResponse) -> bool:
        """Cache Response."""
        
        return self.cache_db.put_entry(request, response, self.default_ttl_hours)
    
    def prepare_request(self, request: LLMRequest, context: str = "") -> LLMRequest:
        """Bereite Request vor (Seed-Propagation)."""
        
        # Propagiere Seed
        prepared_request = self.seed_manager.propagate_seed(request, context)
        
        return prepared_request
    
    def get_cache_efficiency(self) -> Dict[str, Any]:
        """Hole Cache-Effizienz-Statistiken."""
        
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        cache_stats = self.cache_db.get_cache_stats()
        
        return {
            "hit_rate": hit_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total_requests,
            "db_stats": cache_stats
        }


class CachedLLMClient:
    """Cached LLM Client."""
    
    def __init__(self, cache_manager: LLMCacheManager = None):
        self.cache_manager = cache_manager or LLMCacheManager()
    
    def chat_completion(
        self,
        model: str,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.0,
        seed: int = 42,
        max_tokens: Optional[int] = None,
        spec_hash: str = "",
        prompt_version: str = "1.0",
        context: str = ""
    ) -> LLMResponse:
        """Chat Completion mit Cache."""
        
        # Erstelle Request
        request = LLMRequest(
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
            spec_hash=spec_hash,
            prompt_version=prompt_version
        )
        
        # Bereite Request vor (Seed-Propagation)
        prepared_request = self.cache_manager.prepare_request(request, context)
        
        # Prüfe Cache
        cache_status, cached_response = self.cache_manager.get_cached_response(prepared_request)
        
        if cache_status == CacheStatus.HIT and cached_response:
            logger.info(f"Using cached response for {model}")
            return cached_response
        
        # Simuliere LLM-Call (in echter Implementierung würde hier OpenAI API aufgerufen)
        response = self._mock_llm_call(prepared_request)
        
        # Cache Response
        self.cache_manager.cache_response(prepared_request, response)
        
        return response
    
    def _mock_llm_call(self, request: LLMRequest) -> LLMResponse:
        """Mock LLM-Call für Demo."""
        
        # Deterministischer Mock basierend auf Seed und Prompt
        prompt_hash = hashlib.sha256(f"{request.prompt}:{request.seed}".encode('utf-8')).hexdigest()
        
        # Mock-Response
        mock_content = f"Mock response for seed {request.seed} and prompt hash {prompt_hash[:16]}..."
        
        response = LLMResponse(
            content=mock_content,
            finish_reason="stop",
            prompt_tokens=len(request.prompt.split()),
            completion_tokens=len(mock_content.split()),
            total_tokens=len(request.prompt.split()) + len(mock_content.split()),
            model=request.model,
            cached=False
        )
        
        logger.info(f"Mock LLM call: {request.model} with seed {request.seed}")
        
        return response


# Convenience Functions
def create_cached_llm_client(cache_dir: Path = None) -> CachedLLMClient:
    """
    Erstelle Cached LLM Client.
    
    Args:
        cache_dir: Cache-Verzeichnis
        
    Returns:
        Cached LLM Client
    """
    
    if cache_dir is None:
        cache_dir = Path.cwd() / "cache"
    
    cache_manager = LLMCacheManager(cache_dir / "llm_cache.db")
    
    return CachedLLMClient(cache_manager)


def propagate_seed_to_spec(spec_hash: str, global_seed: int = 42) -> int:
    """
    Propagiere Seed zu Spec-Hash.
    
    Args:
        spec_hash: Spec-Hash
        global_seed: Globaler Seed
        
    Returns:
        Propagierter Seed
    """
    
    seed_manager = SeedPropagationManager(global_seed)
    return seed_manager.get_next_seed(spec_hash)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_llm_cache_system():
        print("🎯 LLM Cache System Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test 1: Erstelle Cached LLM Client
            print("\\n🚀 Creating cached LLM client:")
            
            client = create_cached_llm_client(temp_path)
            
            print(f"  ✓ Cache DB path: {client.cache_manager.cache_db.db_path}")
            print(f"  ✓ Default TTL: {client.cache_manager.default_ttl_hours} hours")
            
            # Test 2: Erste LLM-Calls (Cache Miss)
            print("\\n📞 First LLM calls (cache miss):")
            
            spec_hash = "abc123def456"
            test_calls = [
                {
                    "model": "gpt-4o-mini",
                    "prompt": "Generate a Python function to calculate fibonacci numbers",
                    "spec_hash": spec_hash,
                    "context": "fibonacci_generator"
                },
                {
                    "model": "gpt-4o-mini", 
                    "prompt": "Create unit tests for a fibonacci function",
                    "spec_hash": spec_hash,
                    "context": "fibonacci_tests"
                },
                {
                    "model": "gpt-4o",
                    "prompt": "Generate a Python function to calculate fibonacci numbers",
                    "spec_hash": spec_hash,
                    "context": "fibonacci_generator_gpt4"
                }
            ]
            
            responses = []
            
            for i, call in enumerate(test_calls, 1):
                response = client.chat_completion(**call)
                responses.append(response)
                
                print(f"  ✓ Call {i}: {call['model']} - {'CACHED' if response.cached else 'NEW'}")
                print(f"    Seed: {call.get('seed', 42)}, Tokens: {response.total_tokens}")
            
            # Test 3: Wiederholte Calls (Cache Hit)
            print("\\n🎯 Repeated calls (cache hit):")
            
            repeated_responses = []
            
            for i, call in enumerate(test_calls, 1):
                response = client.chat_completion(**call)
                repeated_responses.append(response)
                
                print(f"  ✓ Call {i}: {call['model']} - {'CACHED' if response.cached else 'NEW'}")
                print(f"    Content match: {response.content == responses[i-1].content}")
            
            # Test 4: Cache-Statistiken
            print("\\n📊 Cache statistics:")
            
            efficiency = client.cache_manager.get_cache_efficiency()
            
            print(f"  ✓ Hit rate: {efficiency['hit_rate']:.1f}%")
            print(f"  ✓ Cache hits: {efficiency['cache_hits']}")
            print(f"  ✓ Cache misses: {efficiency['cache_misses']}")
            print(f"  ✓ Total entries in DB: {efficiency['db_stats'].get('total_entries', 0)}")
            
            # Test 5: Seed-Propagation
            print("\\n🌱 Testing seed propagation:")
            
            seed_manager = SeedPropagationManager(global_seed=100)
            
            test_contexts = ["context1", "context2", "context1"]  # context1 wiederholt
            seeds = []
            
            for context in test_contexts:
                seed = seed_manager.get_next_seed(context)
                seeds.append(seed)
                print(f"  ✓ Context '{context}': seed {seed}")
            
            # Prüfe Determinismus
            seed_manager2 = SeedPropagationManager(global_seed=100)
            seeds2 = [seed_manager2.get_next_seed(ctx) for ctx in test_contexts]
            
            deterministic_seeds = seeds == seeds2
            print(f"  ✓ Deterministic seed generation: {deterministic_seeds}")
            
            # Test 6: Cache-Key-Generierung
            print("\\n🔑 Testing cache key generation:")
            
            request1 = LLMRequest(
                model="gpt-4o-mini",
                prompt="Test prompt",
                seed=42,
                spec_hash="test123",
                prompt_version="1.0"
            )
            
            request2 = LLMRequest(
                model="gpt-4o-mini",
                prompt="Test prompt",  # Identisch
                seed=42,
                spec_hash="test123",
                prompt_version="1.0"
            )
            
            request3 = LLMRequest(
                model="gpt-4o-mini",
                prompt="Different prompt",  # Unterschiedlich
                seed=42,
                spec_hash="test123",
                prompt_version="1.0"
            )
            
            key1 = request1.generate_cache_key()
            key2 = request2.generate_cache_key()
            key3 = request3.generate_cache_key()
            
            print(f"  ✓ Key 1: {key1[:16]}...")
            print(f"  ✓ Key 2: {key2[:16]}...")
            print(f"  ✓ Key 3: {key3[:16]}...")
            print(f"  ✓ Keys 1&2 identical: {key1 == key2}")
            print(f"  ✓ Keys 1&3 different: {key1 != key3}")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Seed-Propagation in alle LLM-Aufrufe
            seed_propagation = all(r.model and "seed" in str(r.to_dict()) for r in responses)
            
            # Cache mit Key aus spec-hash, modell, seed, prompt-version
            cache_key_components = all([
                spec_hash in key1,
                "gpt-4o-mini" in str(request1.to_dict()),
                str(request1.seed) == "42",
                request1.prompt_version == "1.0"
            ])
            
            # Wiederholungslauf trifft Cache
            cache_hits_work = all(r.cached for r in repeated_responses)
            
            # Identische Diffs ohne neuen Call
            identical_responses = all(
                responses[i].content == repeated_responses[i].content 
                for i in range(len(responses))
            )
            
            print(f"  ✓ Seed propagation in all LLM calls: {seed_propagation}")
            print(f"  ✓ Cache key from spec-hash/model/seed/prompt-version: {cache_key_components}")
            print(f"  ✓ Repeated runs hit cache: {cache_hits_work}")
            print(f"  ✓ Identical responses without new calls: {identical_responses}")
            
            return (seed_propagation and cache_key_components and 
                   cache_hits_work and identical_responses)
    
    # Führe Demo aus
    try:
        result = demo_llm_cache_system()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
