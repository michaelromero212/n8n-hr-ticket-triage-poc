/**
 * HR Ticket Triage - Form Submission Logic
 */

// API endpoints
const API_BASE = '';  // Same origin
const N8N_WEBHOOK_URL = 'http://localhost:5678/webhook/hr-ticket';

// Form elements
const form = document.getElementById('ticketForm');
const submitBtn = document.getElementById('submitBtn');
const btnText = submitBtn.querySelector('.btn-text');
const btnLoading = submitBtn.querySelector('.btn-loading');
const successModal = document.getElementById('successModal');
const ticketIdSpan = document.getElementById('ticketId');

// AI Status elements
const aiStatus = document.getElementById('aiStatus');
const statusIcon = aiStatus?.querySelector('.status-icon');
const statusText = aiStatus?.querySelector('.status-text');
let aiConnected = false;

/**
 * Check AI health on page load
 */
async function checkAIHealth() {
    if (!aiStatus) return;

    try {
        const response = await fetch('/api/ai/health', { timeout: 8000 });
        const health = await response.json();

        if (health.status === 'connected') {
            statusIcon.textContent = '🟢';
            statusText.textContent = 'AI Connected';
            aiStatus.classList.add('connected');
            submitBtn.disabled = false;
            aiConnected = true;
        } else if (health.status === 'loading') {
            statusIcon.textContent = '🟡';
            statusText.textContent = 'AI Model Loading...';
            aiStatus.classList.add('loading');
            // Retry in 5 seconds
            setTimeout(checkAIHealth, 5000);
        } else {
            statusIcon.textContent = '🔴';
            statusText.textContent = `AI Unavailable: ${health.reason || 'Unknown error'}`;
            aiStatus.classList.add('error');
            submitBtn.disabled = false; // Allow submission anyway, will be pending
            submitBtn.querySelector('.btn-text').textContent = 'Submit (AI Offline)';
        }
    } catch (error) {
        statusIcon.textContent = '🔴';
        statusText.textContent = 'AI Unavailable: Connection error';
        aiStatus.classList.add('error');
        submitBtn.disabled = false;
        submitBtn.querySelector('.btn-text').textContent = 'Submit (AI Offline)';
    }
}

// Check AI health on page load
checkAIHealth();

/**
 * Handle form submission
 */
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Show loading state
    setLoading(true);

    // Collect form data
    const formData = new FormData(form);
    const ticketData = {
        employee_name: formData.get('employee_name'),
        employee_email: formData.get('employee_email'),
        subject: formData.get('subject'),
        description: formData.get('description')
    };

    try {
        // Step 1: Create ticket in our backend
        const ticket = await createTicket(ticketData);

        // Step 2: Trigger n8n workflow for AI classification
        await triggerN8nWorkflow(ticket);

        // Show success
        showSuccess(ticket.id);
        form.reset();

    } catch (error) {
        console.error('Error submitting ticket:', error);
        alert('Failed to submit ticket. Please try again.');
    } finally {
        setLoading(false);
    }
});

/**
 * Create ticket via backend API
 */
async function createTicket(data) {
    const response = await fetch(`${API_BASE}/api/tickets`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });

    if (!response.ok) {
        throw new Error('Failed to create ticket');
    }

    return response.json();
}

/**
 * Trigger n8n workflow for AI classification
 */
async function triggerN8nWorkflow(ticket) {
    try {
        const response = await fetch(N8N_WEBHOOK_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(ticket)
        });

        // n8n might return various responses, we just need to trigger it
        console.log('n8n workflow triggered successfully');
        return response;
    } catch (error) {
        // Don't fail the ticket creation if n8n is not running
        console.warn('Could not reach n8n webhook:', error.message);
        console.log('Ticket created locally. n8n classification pending.');
    }
}

/**
 * Toggle loading state
 */
function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    btnText.style.display = isLoading ? 'none' : 'inline';
    btnLoading.style.display = isLoading ? 'inline-flex' : 'none';
}

/**
 * Show success modal
 */
function showSuccess(ticketId) {
    ticketIdSpan.textContent = ticketId;
    successModal.style.display = 'flex';
}

/**
 * Close success modal
 */
function closeModal() {
    successModal.style.display = 'none';
}

// Close modal on outside click
successModal.addEventListener('click', (e) => {
    if (e.target === successModal) {
        closeModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
});
