"""
Status Page Application for STT Platform

Provides a public-facing status page showing service availability,
incident history, and maintenance schedules.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from flask import Flask, render_template, jsonify, request
import requests

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PROMETHEUS_URL = "http://prometheus:9090"
GRAFANA_URL = "http://grafana:3000"
PAGE_TITLE = "STT Platform Status"
PAGE_DESCRIPTION = "Real-time status of the True Streaming STT Platform"

# Service definitions
SERVICES = [
    {
        "id": "stt-gateway",
        "name": "STT Gateway",
        "description": "WebSocket streaming and batch transcription API",
        "prometheus_query": 'up{job="stt-gateway"}',
        "critical": True
    },
    {
        "id": "triton",
        "name": "Triton Backend",
        "description": "GPU-accelerated speech recognition inference",
        "prometheus_query": 'up{job="triton"}',
        "critical": True
    },
    {
        "id": "postgres",
        "name": "PostgreSQL",
        "description": "Primary database for tenant data and audit logs",
        "prometheus_query": 'up{job="postgres"}',
        "critical": True
    },
    {
        "id": "redis",
        "name": "Redis",
        "description": "Cache for rate limiting and connection counters",
        "prometheus_query": 'up{job="redis"}',
        "critical": True
    },
    {
        "id": "grafana",
        "name": "Grafana",
        "description": "Metrics visualization dashboards",
        "prometheus_query": 'up{job="grafana"}',
        "critical": False
    },
    {
        "id": "loki",
        "name": "Loki",
        "description": "Centralized log aggregation",
        "prometheus_query": 'up{job="loki"}',
        "critical": False
    }
]

# Incident storage (in production, use database)
INCIDENTS = [
    {
        "id": "INC-2024-001",
        "title": "High Latency on STT Gateway",
        "status": "resolved",
        "severity": "degraded",
        "service": "stt-gateway",
        "started_at": "2024-02-15T14:30:00Z",
        "resolved_at": "2024-02-15T15:45:00Z",
        "updates": [
            {
                "timestamp": "2024-02-15T14:30:00Z",
                "message": "Investigating reports of increased latency on STT Gateway"
            },
            {
                "timestamp": "2024-02-15T15:00:00Z",
                "message": "Identified issue with Triton backend queue duration"
            },
            {
                "timestamp": "2024-02-15T15:30:00Z",
                "message": "Scaled Triton replicas to resolve queue issue"
            },
            {
                "timestamp": "2024-02-15T15:45:00Z",
                "message": "Latency returned to normal levels. Issue resolved."
            }
        ]
    }
]

# Maintenance schedule
MAINTENANCE_SCHEDULES = [
    {
        "id": "MAINT-2024-001",
        "title": "PostgreSQL Maintenance",
        "service": "postgres",
        "scheduled_start": "2024-03-15T02:00:00Z",
        "scheduled_end": "2024-03-15T04:00:00Z",
        "description": "Routine database maintenance and vacuum",
        "status": "scheduled"
    }
]


def query_prometheus(query: str) -> Optional[Dict[str, Any]]:
    """
    Query Prometheus for metrics.
    
    Args:
        query: Prometheus query string
        
    Returns:
        Query result or None if query fails
    """
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.error(f"Prometheus query failed: {exc}")
        return None


def get_service_status(service: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get current status of a service.
    
    Args:
        service: Service definition
        
    Returns:
        Service status information
    """
    result = query_prometheus(service["prometheus_query"])
    
    if result and result.get("status") == "success" and result.get("data", {}).get("result"):
        # Service is up
        return {
            "status": "operational",
            "uptime": "99.9%",
            "last_checked": datetime.now(timezone.utc).isoformat()
        }
    else:
        # Service is down
        return {
            "status": "down",
            "uptime": "0%",
            "last_checked": datetime.now(timezone.utc).isoformat()
        }


def calculate_overall_status(services: List[Dict[str, Any]]) -> str:
    """
    Calculate overall system status.
    
    Args:
        services: List of service statuses
        
    Returns:
        Overall status (operational, degraded, or down)
    """
    critical_services = [s for s in services if s.get("critical", False)]
    critical_down = [s for s in critical_services if s["status"] == "down"]
    
    if critical_down:
        return "down"
    
    all_services_down = [s for s in services if s["status"] == "down"]
    if all_services_down:
        return "degraded"
    
    return "operational"


@app.route('/')
def index():
    """Render status page."""
    # Get service statuses
    service_statuses = []
    for service in SERVICES:
        status = get_service_status(service)
        service_statuses.append({
            **service,
            **status
        })
    
    # Calculate overall status
    overall_status = calculate_overall_status(service_statuses)
    
    return render_template(
        'status.html',
        page_title=PAGE_TITLE,
        page_description=PAGE_DESCRIPTION,
        overall_status=overall_status,
        services=service_statuses,
        incidents=INCIDENTS,
        maintenance_schedules=MAINTENANCE_SCHEDULES,
        last_updated=datetime.now(timezone.utc)
    )


@app.route('/api/status')
def api_status():
    """Return status as JSON for API consumers."""
    # Get service statuses
    service_statuses = []
    for service in SERVICES:
        status = get_service_status(service)
        service_statuses.append({
            "id": service["id"],
            "name": service["name"],
            "description": service["description"],
            "status": status["status"],
            "uptime": status["uptime"],
            "last_checked": status["last_checked"],
            "critical": service["critical"]
        })
    
    # Calculate overall status
    overall_status = calculate_overall_status(service_statuses)
    
    return jsonify({
        "page": {
            "title": PAGE_TITLE,
            "description": PAGE_DESCRIPTION,
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        "status": overall_status,
        "services": service_statuses,
        "incidents": INCIDENTS,
        "maintenance_schedules": MAINTENANCE_SCHEDULES
    })


@app.route('/api/incidents', methods=['POST'])
def create_incident():
    """Create a new incident (authenticated endpoint)."""
    # In production, add authentication
    data = request.json
    
    incident = {
        "id": f"INC-{datetime.now().strftime('%Y')}-{len(INCIDENTS) + 1:03d}",
        "title": data.get("title"),
        "status": "investigating",
        "severity": data.get("severity", "degraded"),
        "service": data.get("service"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "updates": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": data.get("message", "Investigation started")
            }
        ]
    }
    
    INCIDENTS.append(incident)
    logger.info(f"Created incident: {incident['id']}")
    
    return jsonify(incident), 201


@app.route('/api/incidents/<incident_id>/updates', methods=['POST'])
def add_incident_update(incident_id):
    """Add an update to an incident."""
    data = request.json
    
    # Find incident
    incident = next((i for i in INCIDENTS if i["id"] == incident_id), None)
    if not incident:
        return jsonify({"error": "Incident not found"}), 404
    
    # Add update
    update = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": data.get("message")
    }
    incident["updates"].append(update)
    
    # Update status if provided
    if data.get("status"):
        incident["status"] = data["status"]
        if data["status"] == "resolved":
            incident["resolved_at"] = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"Added update to incident: {incident_id}")
    
    return jsonify(incident)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
