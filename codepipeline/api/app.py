"""
CodePipeline API App - Unified FastAPI Application.

Implementiert:
- BL-001: API-Shim wiring vereinheitlichen
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from fastapi import FastAPI, HTTPException, Depends
    from fastapi.responses import JSONResponse, PlainTextResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    # Fallback for environments without FastAPI
    FASTAPI_AVAILABLE = False
    FastAPI = None
    HTTPException = None
    BaseModel = None

# Import CodePipeline components
from ..secure_smoke_test import SecureSmokeTestRunner, SmokeTestSpec
from ..lean_gui_suite import LeanGUISuite


# === BL-001: API-Shim wiring vereinheitlichen ===

class HealthResponse(BaseModel if FASTAPI_AVAILABLE else object):
    """Health check response."""
    
    status: str = "ok"
    timestamp: str = ""
    version: str = "1.0.0"
    components: Dict[str, str] = {}
    
    def __init__(self, **data):
        if FASTAPI_AVAILABLE:
            super().__init__(**data)
        else:
            # Simple fallback for non-FastAPI environments
            self.status = data.get("status", "ok")
            self.timestamp = data.get("timestamp", datetime.utcnow().isoformat())
            self.version = data.get("version", "1.0.0")
            self.components = data.get("components", {})


class SmokeTestRequest(BaseModel if FASTAPI_AVAILABLE else object):
    """Smoke test request."""
    
    prompt: str
    template_type: str = "web-api"
    secure_mode: bool = True
    budget_limit_tokens: int = 500
    timeout_seconds: int = 30
    
    def __init__(self, **data):
        if FASTAPI_AVAILABLE:
            super().__init__(**data)
        else:
            # Simple fallback
            self.prompt = data.get("prompt", "")
            self.template_type = data.get("template_type", "web-api")
            self.secure_mode = data.get("secure_mode", True)
            self.budget_limit_tokens = data.get("budget_limit_tokens", 500)
            self.timeout_seconds = data.get("timeout_seconds", 30)


class CodePipelineAPI:
    """CodePipeline API implementation."""
    
    def __init__(self):
        self.smoke_test_runner = SecureSmokeTestRunner()
        self.gui_suite = LeanGUISuite()
        self.start_time = datetime.utcnow()
        
        # Initialize FastAPI app if available
        if FASTAPI_AVAILABLE:
            self.app = FastAPI(
                title="CodePipeline API",
                description="Enterprise-Grade Pipeline for Automated Software Development",
                version="1.0.0"
            )
            self._setup_routes()
            self._setup_middleware()
        else:
            # Create a minimal app-like object for compatibility
            self.app = self._create_fallback_app()
    
    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        if not FASTAPI_AVAILABLE:
            return
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        if not FASTAPI_AVAILABLE:
            return
        
        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            return await self.get_health()
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return {"message": "CodePipeline API", "version": "1.0.0", "status": "ready"}
        
        @self.app.post("/smoke-test")
        async def run_smoke_test(request: SmokeTestRequest):
            """Run secure smoke test."""
            try:
                spec = SmokeTestSpec(
                    prompt=request.prompt,
                    template_type=request.template_type,
                    secure_mode=request.secure_mode,
                    budget_limit_tokens=request.budget_limit_tokens,
                    timeout_seconds=request.timeout_seconds
                )
                
                result = self.smoke_test_runner.engine.run_smoke_test(spec)
                summary = self.smoke_test_runner.engine.generate_summary_markdown(result)
                
                return {
                    "result": result.to_dict(),
                    "summary": summary,
                    "status": "completed"
                }
                
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/gui/dashboard")
        async def get_dashboard_data():
            """Get GUI dashboard data."""
            try:
                dashboard_data = self.gui_suite.get_dashboard_data()
                return dashboard_data
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    def _create_fallback_app(self):
        """Create fallback app object for non-FastAPI environments."""
        
        class FallbackApp:
            def __init__(self, api_instance):
                self.api = api_instance
                self.routes = [
                    {"path": "/health", "method": "GET"},
                    {"path": "/", "method": "GET"},
                    {"path": "/smoke-test", "method": "POST"},
                    {"path": "/gui/dashboard", "method": "GET"}
                ]
            
            def openapi(self):
                """Return OpenAPI schema."""
                return {
                    "openapi": "3.0.0",
                    "info": {
                        "title": "CodePipeline API",
                        "version": "1.0.0",
                        "description": "Enterprise-Grade Pipeline for Automated Software Development"
                    },
                    "paths": {
                        "/health": {
                            "get": {
                                "summary": "Health Check",
                                "responses": {
                                    "200": {"description": "Health status"}
                                }
                            }
                        },
                        "/smoke-test": {
                            "post": {
                                "summary": "Run Smoke Test",
                                "responses": {
                                    "200": {"description": "Smoke test results"}
                                }
                            }
                        }
                    }
                }
            
            async def handle_request(self, path: str, method: str, data: Optional[Dict] = None):
                """Handle request (fallback implementation)."""
                if path == "/health" and method == "GET":
                    return await self.api.get_health()
                elif path == "/" and method == "GET":
                    return {"message": "CodePipeline API", "version": "1.0.0", "status": "ready"}
                elif path == "/smoke-test" and method == "POST":
                    if not data or "prompt" not in data:
                        raise ValueError("Prompt required")
                    
                    spec = SmokeTestSpec(
                        prompt=data["prompt"],
                        template_type=data.get("template_type", "web-api"),
                        secure_mode=data.get("secure_mode", True),
                        budget_limit_tokens=data.get("budget_limit_tokens", 500),
                        timeout_seconds=data.get("timeout_seconds", 30)
                    )
                    
                    result = self.api.smoke_test_runner.engine.run_smoke_test(spec)
                    summary = self.api.smoke_test_runner.engine.generate_summary_markdown(result)
                    
                    return {
                        "result": result.to_dict(),
                        "summary": summary,
                        "status": "completed"
                    }
                elif path == "/gui/dashboard" and method == "GET":
                    return self.api.gui_suite.get_dashboard_data()
                else:
                    raise ValueError(f"Unknown endpoint: {method} {path}")
        
        return FallbackApp(self)
    
    async def get_health(self) -> HealthResponse:
        """Get health status."""
        
        # Check component health
        components = {}
        
        try:
            # Test smoke test runner
            self.smoke_test_runner.engine
            components["smoke_test_runner"] = "healthy"
        except Exception:
            components["smoke_test_runner"] = "unhealthy"
        
        try:
            # Test GUI suite
            self.gui_suite.get_suite_status()
            components["gui_suite"] = "healthy"
        except Exception:
            components["gui_suite"] = "unhealthy"
        
        # Check if FastAPI is available
        components["fastapi"] = "available" if FASTAPI_AVAILABLE else "unavailable"
        
        return HealthResponse(
            status="ok",
            timestamp=datetime.utcnow().isoformat(),
            version="1.0.0",
            components=components
        )


# Global API instance
_api_instance = None


def get_api_instance() -> CodePipelineAPI:
    """Get or create API instance."""
    global _api_instance
    if _api_instance is None:
        _api_instance = CodePipelineAPI()
    return _api_instance


# Export the app object for BL-001 compliance
api_instance = get_api_instance()
app = api_instance.app


# Convenience functions for direct access
async def health_check() -> Dict[str, Any]:
    """Direct health check function."""
    health_response = await api_instance.get_health()
    if hasattr(health_response, "dict"):
        return health_response.dict()
    else:
        return {
            "status": health_response.status,
            "timestamp": health_response.timestamp,
            "version": health_response.version,
            "components": health_response.components
        }


def run_minimal_smoke_test(prompt: str) -> Dict[str, Any]:
    """Run minimal smoke test for API validation."""
    spec = SmokeTestSpec(
        prompt=prompt,
        budget_limit_tokens=200,
        timeout_seconds=15
    )
    
    result = api_instance.smoke_test_runner.engine.run_smoke_test(spec)
    
    return {
        "test_id": result.test_id,
        "status": result.overall_status,
        "duration": result.total_duration_seconds,
        "tokens_used": result.total_tokens_used,
        "gates_passed": len([g for g in result.gates if g.status == "pass"]),
        "total_gates": len(result.gates)
    }


if __name__ == "__main__":
    # Demo/Test mode
    import asyncio
    
    async def demo_api():
        print("CodePipeline API Demo:")
        
        # Test 1: Health check
        print("\\n1. Health check:")
        health = await health_check()
        print(f"   Status: {health['status']}")
        print(f"   Components: {health['components']}")
        
        # Test 2: Minimal smoke test
        print("\\n2. Minimal smoke test:")
        smoke_result = run_minimal_smoke_test("Simple REST API for user management")
        print(f"   Test ID: {smoke_result['test_id']}")
        print(f"   Status: {smoke_result['status']}")
        print(f"   Duration: {smoke_result['duration']:.1f}s")
        print(f"   Gates: {smoke_result['gates_passed']}/{smoke_result['total_gates']}")
        
        # Test 3: App object validation
        print("\\n3. App object validation:")
        print(f"   App type: {type(app).__name__}")
        print(f"   Has openapi: {hasattr(app, 'openapi')}")
        print(f"   Has routes: {hasattr(app, 'routes')}")
        
        if hasattr(app, 'openapi'):
            openapi_schema = app.openapi()
            print(f"   OpenAPI title: {openapi_schema.get('info', {}).get('title', 'N/A')}")
        
        print("\\nAPI Demo completed!")
    
    # Run demo
    asyncio.run(demo_api())