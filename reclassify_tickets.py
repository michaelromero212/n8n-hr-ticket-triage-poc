#!/usr/bin/env python3
"""
Script to re-classify pending tickets using the HuggingFace API.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / '.env')

TICKETS_FILE = Path(__file__).parent / 'data' / 'tickets.json'
HUGGINGFACE_API_URL = "https://router.huggingface.co/hf-inference/models/MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
CANDIDATE_LABELS = ["Benefits", "PTO", "Payroll", "Policy", "Onboarding", "Offboarding", "Complaint", "General"]


def load_tickets():
    with open(TICKETS_FILE, 'r') as f:
        return json.load(f)


def save_tickets(tickets):
    with open(TICKETS_FILE, 'w') as f:
        json.dump(tickets, f, indent=2, default=str)


def classify_ticket(description: str) -> dict:
    """Classify ticket using HuggingFace zero-shot classification."""
    token = os.getenv('HUGGINGFACE_API_TOKEN')
    if not token:
        print("❌ No HuggingFace API token found!")
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
        
        # Parse response
        if isinstance(result, list) and len(result) > 0:
            if 'label' in result[0] and 'score' in result[0]:
                return {
                    'category': result[0]['label'],
                    'confidence': result[0]['score']
                }
        
        if 'labels' in result and 'scores' in result:
            return {
                'category': result['labels'][0],
                'confidence': result['scores'][0]
            }
            
    except Exception as e:
        print(f"❌ Classification error: {e}")
    
    return None


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


def main():
    print("🔄 Re-classifying pending tickets...\n")
    
    tickets = load_tickets()
    pending_tickets = [t for t in tickets if t.get('status') == 'pending']
    
    print(f"Found {len(pending_tickets)} pending tickets to classify\n")
    
    for ticket in pending_tickets:
        print(f"📋 Processing: {ticket['id'][:8]}... - {ticket['subject']}")
        
        classification = classify_ticket(ticket['description'])
        
        if classification:
            ticket['ai_category'] = classification['category']
            ticket['ai_confidence'] = classification['confidence']
            ticket['status'] = 'classified'
            ticket['ai_response'] = generate_auto_response(classification['category'])
            ticket['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            print(f"   ✅ Classified as: {classification['category']} ({classification['confidence']*100:.1f}% confidence)")
        else:
            print(f"   ❌ Classification failed")
    
    save_tickets(tickets)
    print(f"\n✅ Done! Processed {len(pending_tickets)} tickets.")


if __name__ == '__main__':
    main()
