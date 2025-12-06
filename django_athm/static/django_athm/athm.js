/* ATH Móvil Payment Modal - Minimal JavaScript */

// Global state
let athmPaymentData = {};
let athmPollingInterval = null;
let athmCurrentLang = 'es';

/**
 * Open ATH Móvil payment modal
 */
function openATHMModal(button) {
    // Extract data from button
    athmPaymentData = {
        total: button.getAttribute('data-athm-total'),
        subtotal: button.getAttribute('data-athm-subtotal'),
        tax: button.getAttribute('data-athm-tax'),
        metadata1: button.getAttribute('data-athm-metadata1'),
        metadata2: button.getAttribute('data-athm-metadata2'),
        timeout: parseInt(button.getAttribute('data-athm-timeout')) || 600,
    };

    athmCurrentLang = button.getAttribute('data-athm-lang') || 'es';

    // Update modal language
    updateModalLanguage();

    // Show modal and phone step
    document.getElementById('athm-modal').style.display = 'flex';
    showATHMStep('phone');

    // Display total in modal
    document.getElementById('athm-total-display').textContent = formatCurrency(athmPaymentData.total);
}

/**
 * Close ATH Móvil payment modal
 */
function closeATHMModal() {
    // Stop polling
    if (athmPollingInterval) {
        clearInterval(athmPollingInterval);
        athmPollingInterval = null;
    }

    // Hide modal
    document.getElementById('athm-modal').style.display = 'none';

    // Reset to phone step
    showATHMStep('phone');

    // Clear form
    document.getElementById('athm-phone-form').reset();
    document.getElementById('athm-error-message').style.display = 'none';
}

/**
 * Show specific modal step
 */
function showATHMStep(step) {
    const steps = ['phone', 'loading', 'success', 'error'];
    steps.forEach(s => {
        const el = document.getElementById(`athm-step-${s}`);
        if (el) {
            el.style.display = s === step ? 'block' : 'none';
        }
    });
}

/**
 * Update modal language
 */
function updateModalLanguage() {
    const elements = document.querySelectorAll('[data-en][data-es]');
    elements.forEach(el => {
        const text = el.getAttribute(`data-${athmCurrentLang}`);
        if (text) {
            el.textContent = text;
        }
    });
}

/**
 * Submit phone number and create payment
 */
function submitPhoneNumber(event) {
    event.preventDefault();

    const phoneInput = document.getElementById('athm-phone-input');
    const phoneNumber = phoneInput.value.trim();

    // Show loading
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = athmCurrentLang === 'en' ? 'Processing...' : 'Procesando...';

    // Hide previous errors
    document.getElementById('athm-error-message').style.display = 'none';

    // Get CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    // Create payment
    const formData = new FormData();
    formData.append('phone_number', phoneNumber);
    formData.append('total', athmPaymentData.total);
    if (athmPaymentData.subtotal) formData.append('subtotal', athmPaymentData.subtotal);
    if (athmPaymentData.tax) formData.append('tax', athmPaymentData.tax);
    if (athmPaymentData.metadata1) formData.append('metadata1', athmPaymentData.metadata1);
    if (athmPaymentData.metadata2) formData.append('metadata2', athmPaymentData.metadata2);

    fetch('/athm/create-payment/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
        },
        body: formData,
    })
        .then(response => response.json())
        .then(data => {
            submitBtn.disabled = false;
            submitBtn.textContent = athmCurrentLang === 'en' ? 'Send Payment Request' : 'Enviar Solicitud de Pago';

            if (data.error) {
                showError(data.error);
                return;
            }

            // Store ecommerce_id for polling
            athmPaymentData.ecommerce_id = data.ecommerce_id;
            athmPaymentData.transaction_id = data.transaction_id;

            // Show loading step and start polling
            showATHMStep('loading');
            document.getElementById('athm-loading-total').textContent = formatCurrency(athmPaymentData.total);
            startPolling();
        })
        .catch(error => {
            submitBtn.disabled = false;
            submitBtn.textContent = athmCurrentLang === 'en' ? 'Send Payment Request' : 'Enviar Solicitud de Pago';
            showError(athmCurrentLang === 'en' ? 'Network error. Please try again.' : 'Error de red. Por favor intenta de nuevo.');
            console.error('Payment creation error:', error);
        });
}

/**
 * Show error message
 */
function showError(message) {
    const errorEl = document.getElementById('athm-error-message');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

/**
 * Start polling for payment status
 */
function startPolling() {
    let pollCount = 0;
    const maxPolls = Math.floor(athmPaymentData.timeout / 2); // Poll every 2 seconds

    athmPollingInterval = setInterval(() => {
        pollCount++;

        if (pollCount > maxPolls) {
            // Timeout
            clearInterval(athmPollingInterval);
            showATHMStep('error');
            document.getElementById('athm-error-title').textContent = athmCurrentLang === 'en' ? 'Payment Expired' : 'Pago Expirado';
            document.getElementById('athm-error-description').textContent = athmCurrentLang === 'en' ? 'The payment request has expired.' : 'La solicitud de pago ha expirado.';
            return;
        }

        // Poll status
        fetch(`/athm/payment-status/${athmPaymentData.ecommerce_id}/`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('Polling error:', data.error);
                    return;
                }

                // Update reference number if available
                if (data.reference_number) {
                    document.getElementById('athm-loading-reference').textContent = data.reference_number;
                }

                // Check status
                if (data.status === 'COMPLETED') {
                    clearInterval(athmPollingInterval);
                    showSuccess(data.reference_number);
                } else if (data.status === 'CANCELLED') {
                    clearInterval(athmPollingInterval);
                    showATHMStep('error');
                    document.getElementById('athm-error-title').textContent = athmCurrentLang === 'en' ? 'Payment Cancelled' : 'Pago Cancelado';
                    document.getElementById('athm-error-description').textContent = athmCurrentLang === 'en' ? 'The payment was cancelled.' : 'El pago fue cancelado.';
                } else if (data.status === 'EXPIRED') {
                    clearInterval(athmPollingInterval);
                    showATHMStep('error');
                    document.getElementById('athm-error-title').textContent = athmCurrentLang === 'en' ? 'Payment Expired' : 'Pago Expirado';
                    document.getElementById('athm-error-description').textContent = athmCurrentLang === 'en' ? 'The payment request has expired.' : 'La solicitud de pago ha expirado.';
                }
            })
            .catch(error => {
                console.error('Polling network error:', error);
            });
    }, 2000); // Poll every 2 seconds
}

/**
 * Show success step
 */
function showSuccess(referenceNumber) {
    showATHMStep('success');
    document.getElementById('athm-success-total').textContent = formatCurrency(athmPaymentData.total);
    document.getElementById('athm-success-reference').textContent = referenceNumber || '-';
}

/**
 * Format currency for display
 */
function formatCurrency(amount) {
    const num = parseFloat(amount);
    if (isNaN(num)) return '$0.00';
    return `$${num.toFixed(2)}`;
}
