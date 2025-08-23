#!/usr/bin/env python3
"""
Minimalistische Web-API mit Health-Route und Verdoppelungs-Endpoint.
Generiert durch CodePipeline One-Prompt-to-Deploy.
"""

from flask import Flask, jsonify, request
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route('/health', methods=['GET'])
def health():
    """Health-Check Endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "double_api",
        "version": "1.0.0"
    }), 200


@app.route('/double', methods=['POST'])
def double_number():
    """Verdoppelt eine Zahl."""
    try:
        data = request.get_json()
        
        if not data or 'number' not in data:
            return jsonify({"error": "Missing 'number' field"}), 400
        
        number = data['number']
        if not isinstance(number, (int, float)):
            return jsonify({"error": "Field 'number' must be numeric"}), 400
        
        result = number * 2
        logger.info(f"Doubled {number} to {result}")
        
        return jsonify({
            "input": number,
            "result": result,
            "operation": "double"
        }), 200
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/', methods=['GET'])
def root():
    """Root endpoint mit API-Info."""
    return jsonify({
        "service": "double_api",
        "version": "1.0.0",
        "endpoints": {
            "/health": "GET - Health check",
            "/double": "POST - Double a number"
        }
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
