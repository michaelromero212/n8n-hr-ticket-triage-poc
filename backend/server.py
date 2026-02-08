"""
HR Ticket Triage POC - Backend Server

Simple Flask server that:
1. Serves the frontend static files
2. Provides REST API for ticket management
3. Handles n8n webhook callbacks
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from project root
load_dotenv(Path(__file__).parent.parent / '.env')

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)  # Allow n8n to call our API

# Data file path
DATA_DIR = Path(__file__).parent.parent / 'data'
TICKETS_FILE = DATA_DIR / 'tickets.json'


def load_tickets():
    """Load tickets from JSON file."""
    if TICKETS_FILE.exists():
        with open(TICKETS_FILE, 'r') as f:
            return json.load(f)
    return []


def save_tickets(tickets):
    """Save tickets to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(TICKETS_FILE, 'w') as f:
        json.dump(tickets, f, indent=2, default=str)


# ============== AI Classification ==============

import requests

HUGGINGFACE_API_URL = "https://router.huggingface.co/hf-inference/models/MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
CANDIDATE_LABELS = ["Benefits", "PTO", "Payroll", "Policy", "Onboarding", "Offboarding", "Complaint", "General"]


def classify_ticket(description: str) -> Optional[dict]:
    """Classify ticket using HuggingFace zero-shot classification."""
    token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not token or not description:
        print("⚠️ AI Classification skipped: No token or description")
        return None
    
    try:
        response = requests.post(
            HUGGINGFACE_API_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": description,
                "parameters": {"candidate_labels": CANDIDATE_LABELS}
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"🤖 AI API Response: {result}")
        
        # New format: list of {label, score} objects sorted by score descending
        if isinstance(result, list) and len(result) > 0:
            # Each item has 'label' and 'score' keys
            if 'label' in result[0] and 'score' in result[0]:
                return {
                    'category': result[0]['label'],
                    'confidence': result[0]['score']
                }
            # Nested list format
            elif isinstance(result[0], list) and len(result[0]) > 0:
                first_item = result[0][0]
                if 'label' in first_item:
                    return {
                        'category': first_item['label'],
                        'confidence': first_item['score']
                    }
        
        # Old format: {labels: [], scores: []}
        if 'labels' in result and 'scores' in result:
            return {
                'category': result['labels'][0],
                'confidence': result['scores'][0]
            }
            
        print(f"⚠️ Unexpected API response format: {result}")
    except Exception as e:
        print(f"⚠️ AI Classification error: {e}")
    
    return None


# ============== n8n Webhook Integration ==============

N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://mikesautomations.app.n8n.cloud/webhook-test/0290f3c9-3702-4908-8d47-b60b4ef53924')


def trigger_n8n_workflow(ticket: dict) -> dict:
    """Send ticket data to n8n webhook to trigger automation workflow."""
    if not N8N_WEBHOOK_URL:
        print("⚠️ n8n webhook not configured")
        return {'success': False, 'error': 'No webhook URL configured'}
    
    try:
        print(f"🔗 Triggering n8n workflow for ticket: {ticket['id']}")
        response = requests.post(
            N8N_WEBHOOK_URL,
            json={
                'ticket_id': ticket['id'],
                'employee_name': ticket['employee_name'],
                'employee_email': ticket['employee_email'],
                'subject': ticket['subject'],
                'description': ticket['description'],
                'ai_category': ticket.get('ai_category'),
                'ai_confidence': ticket.get('ai_confidence'),
                'status': ticket['status'],
                'created_at': ticket['created_at']
            },
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ n8n workflow triggered successfully")
            return {'success': True, 'status_code': response.status_code}
        else:
            print(f"⚠️ n8n webhook returned {response.status_code}: {response.text}")
            return {'success': False, 'status_code': response.status_code}
            
    except requests.exceptions.Timeout:
        print("⚠️ n8n webhook timeout")
        return {'success': False, 'error': 'Webhook timeout'}
    except Exception as e:
        print(f"⚠️ n8n webhook error: {e}")
        return {'success': False, 'error': str(e)}


def generate_auto_response(category: str) -> str:
    """Generate a suggested response based on category."""
    responses = {
        'Benefits': "Thank you for your benefits inquiry. Our HR Benefits team will review your request and respond within 24-48 hours. In the meantime, you can check our Benefits portal at hr.company.com/benefits.",
        'PTO': "Your PTO request has been received. Please ensure your manager approves the request in the HR system. Standard PTO requests are processed within 1 business day.",
        'Payroll': "We've received your payroll inquiry. Our payroll team processes requests within 2 business days. For urgent matters, please contact payroll@company.com directly.",
        'Policy': "Thank you for your policy question. Our HR team will provide guidance within 24 hours. You can also reference the employee handbook at hr.company.com/policies.",
        'Onboarding': "Welcome! Your onboarding question has been routed to our New Hire team. They will reach out within 24 hours to assist you.",
        'Offboarding': "Your offboarding inquiry has been received. Our HR team will contact you to discuss next steps and ensure a smooth transition.",
        'Complaint': "We take all workplace concerns seriously. Your matter has been flagged for priority review. An HR representative will contact you within 24 hours.",
        'General': "Thank you for contacting HR. Your request has been received and will be addressed within 24-48 hours."
    }
    return responses.get(category, responses['General'])


def check_ai_health() -> dict:
    """Check if HuggingFace API is responsive with a quick test."""
    token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not token:
        return {'status': 'disconnected', 'reason': 'No API token configured'}
    
    try:
        # Quick test with minimal input and short timeout
        response = requests.post(
            HUGGINGFACE_API_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": "test",
                "parameters": {"candidate_labels": ["test"]}
            },
            timeout=5  # Short timeout for health check
        )
        if response.status_code == 200:
            return {'status': 'connected', 'model': 'facebook/bart-large-mnli'}
        elif response.status_code == 503:
            return {'status': 'loading', 'reason': 'Model is loading, please wait'}
        else:
            return {'status': 'error', 'reason': f'API returned {response.status_code}'}
    except requests.exceptions.Timeout:
        return {'status': 'timeout', 'reason': 'API not responding'}
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}


@app.route('/api/ai/health', methods=['GET'])
def ai_health():
    """Check AI classification service health."""
    health = check_ai_health()
    status_code = 200 if health['status'] == 'connected' else 503
    return jsonify(health), status_code


# ============== Static Files ==============

@app.route('/')
def serve_index():
    """Serve the ticket submission form."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/dashboard')
def serve_dashboard():
    """Serve the dashboard page."""
    return send_from_directory(app.static_folder, 'dashboard.html')


@app.route('/how-it-works')
def serve_how_it_works():
    """Serve the How It Works page."""
    return send_from_directory(app.static_folder, 'how-it-works.html')


@app.route('/workflows')
def serve_workflows():
    """Serve the Workflows Gallery page."""
    return send_from_directory(app.static_folder, 'workflows.html')


@app.route('/integrations-demo')
def serve_integrations_demo():
    """Serve the Integrations Demo page."""
    return send_from_directory(app.static_folder, 'integrations-demo.html')


@app.route('/api/workflows/<filename>')
def serve_workflow_json(filename):
    """Serve n8n workflow JSON files for download."""
    workflows_dir = Path(__file__).parent.parent / 'n8n-workflows'
    return send_from_directory(workflows_dir, filename)


# ============== Ticket API ==============

@app.route('/api/tickets', methods=['GET'])
def get_tickets():
    """Get all tickets."""
    tickets = load_tickets()
    return jsonify(tickets)


@app.route('/api/tickets', methods=['POST'])
def create_ticket():
    """Create a new ticket - returns immediately, processes AI in background."""
    data = request.json
    
    ticket = {
        'id': str(uuid4()),
        'employee_name': data.get('employee_name', ''),
        'employee_email': data.get('employee_email', ''),
        'subject': data.get('subject', ''),
        'description': data.get('description', ''),
        'status': 'pending',
        'ai_category': None,
        'ai_confidence': None,
        'ai_response': None,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Save ticket immediately (pending status)
    tickets = load_tickets()
    tickets.append(ticket)
    save_tickets(tickets)
    
    # Process AI classification and n8n in background thread
    import threading
    def process_ticket_async(ticket_id):
        """Background task to classify ticket and trigger n8n."""
        try:
            tickets = load_tickets()
            ticket = next((t for t in tickets if t['id'] == ticket_id), None)
            if not ticket:
                return
            
            # Classify with AI
            classification = classify_ticket(ticket['description'])
            if classification:
                ticket['ai_category'] = classification['category']
                ticket['ai_confidence'] = classification['confidence']
                ticket['status'] = 'classified'
                ticket['ai_response'] = generate_auto_response(classification['category'])
                ticket['updated_at'] = datetime.now(timezone.utc).isoformat()
                save_tickets(tickets)
                print(f"✅ Async: Ticket {ticket_id[:8]} classified as {classification['category']}")
            
            # Trigger n8n workflow
            trigger_n8n_workflow(ticket)
            
        except Exception as e:
            print(f"❌ Async processing error: {e}")
    
    # Start background processing
    thread = threading.Thread(target=process_ticket_async, args=(ticket['id'],))
    thread.daemon = True
    thread.start()
    
    # Return immediately with pending ticket
    return jsonify(ticket), 201


@app.route('/api/tickets/<ticket_id>', methods=['PATCH'])
def update_ticket(ticket_id):
    """Update a ticket (called from n8n after AI classification)."""
    data = request.json
    tickets = load_tickets()
    
    for ticket in tickets:
        if ticket['id'] == ticket_id:
            ticket['ai_category'] = data.get('ai_category', ticket.get('ai_category'))
            ticket['ai_confidence'] = data.get('ai_confidence', ticket.get('ai_confidence'))
            ticket['ai_response'] = data.get('ai_response', ticket.get('ai_response'))
            ticket['status'] = data.get('status', 'classified')
            ticket['updated_at'] = datetime.now(timezone.utc).isoformat()
            save_tickets(tickets)
            return jsonify(ticket)
    
    return jsonify({'error': 'Ticket not found'}), 404


@app.route('/api/tickets/<ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    """Get a single ticket by ID."""
    tickets = load_tickets()
    for ticket in tickets:
        if ticket['id'] == ticket_id:
            return jsonify(ticket)
    return jsonify({'error': 'Ticket not found'}), 404


@app.route('/api/tickets/<ticket_id>/resolve', methods=['POST'])
def resolve_ticket(ticket_id):
    """Resolve a ticket via the dashboard UI."""
    data = request.json or {}
    action = data.get('action', 'resolved')  # 'resolved' or 'escalated'
    
    tickets = load_tickets()
    for ticket in tickets:
        if ticket['id'] == ticket_id:
            ticket['status'] = action
            ticket['updated_at'] = datetime.now(timezone.utc).isoformat()
            ticket['resolved_by'] = data.get('user', 'Dashboard User')
            save_tickets(tickets)
            print(f"✅ Ticket {ticket_id} marked as {action}")
            return jsonify({
                'success': True,
                'ticket_id': ticket_id,
                'status': action,
                'message': f'Ticket {action} successfully'
            })
    
    return jsonify({'error': 'Ticket not found'}), 404


# ============== Analytics API ==============

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get ticket analytics for dashboard."""
    tickets = load_tickets()
    
    # Category counts
    category_counts = {}
    for ticket in tickets:
        cat = ticket.get('ai_category') or 'Unclassified'
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # Status counts
    status_counts = {}
    for ticket in tickets:
        status = ticket.get('status', 'pending')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return jsonify({
        'total_tickets': len(tickets),
        'category_counts': category_counts,
        'status_counts': status_counts
    })


# ============== Health Check ==============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'n8n_webhook_url': os.getenv('N8N_WEBHOOK_URL', 'not configured')
    })


if __name__ == '__main__':
    print("🚀 Starting HR Ticket Triage Backend...")
    print(f"📁 Serving frontend from: {app.static_folder}")
    print(f"📊 Tickets stored in: {TICKETS_FILE}")
    print(f"🔗 n8n Webhook URL: {os.getenv('N8N_WEBHOOK_URL', 'not configured')}")
    print("\n🌐 Open http://localhost:5001 in your browser\n")
    app.run(host='0.0.0.0', port=5001, debug=True)
