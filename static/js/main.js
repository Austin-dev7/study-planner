// ===== CSRF Protection for AJAX requests =====
// Attach the CSRF token to all non-GET fetch requests automatically.
(function() {
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (!csrfToken) return;

    const token = csrfToken.getAttribute('content');
    const originalFetch = window.fetch;

    window.fetch = function(input, init) {
        init = init || {};
        const method = (init.method || 'GET').toUpperCase();

        if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
            // Set the X-CSRFToken header expected by Flask-WTF
            init.headers = init.headers || {};
            if (init.headers instanceof Headers) {
                init.headers.set('X-CSRFToken', token);
            } else {
                init.headers['X-CSRFToken'] = token;
            }
        }

        return originalFetch(input, init);
    };
})();

// Mobile Sidebar Toggle
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar'); 
    sidebar.classList.toggle('open');
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', function(e) {
    const sidebar = document.querySelector('.sidebar');
    const toggle = document.querySelector('.menu-toggle');

    if (window.innerWidth <= 768 && 
        sidebar.classList.contains('open') && 
        !sidebar.contains(e.target) && 
        !toggle.contains(e.target)) {
        sidebar.classList.remove('open');
    }
});

// Smooth page transitions
document.addEventListener('DOMContentLoaded', function() {
    // Add fade-in animation to main content
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.style.opacity = '0';
        mainContent.style.transform = 'translateY(10px)';
        mainContent.style.transition = 'opacity 0.3s ease, transform 0.3s ease';

        setTimeout(() => {
            mainContent.style.opacity = '1';
            mainContent.style.transform = 'translateY(0)';
        }, 50);
    }

    // Animate stat cards on load
    const statCards = document.querySelectorAll('.stat-card');
    statCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';

        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 100 * (index + 1));
    });
});

// Form validation helpers
function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            isValid = false;
            input.style.borderColor = 'var(--danger)';

            // Remove error style on input
            input.addEventListener('input', function() {
                this.style.borderColor = 'var(--border-color)';
            }, { once: true });
        }
    });

    return isValid;
}

// Add form validation to all forms
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function(e) {
        if (!validateForm(this)) {
            e.preventDefault();
        }
    });
});

// Task completion animation
function animateTaskComplete(taskElement) {
    taskElement.style.transition = 'all 0.5s ease';
    taskElement.style.opacity = '0';
    taskElement.style.transform = 'translateX(100px)';

    setTimeout(() => {
        taskElement.remove();
    }, 500);
}

// Toast notification helper
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'success' ? 'var(--success)' : 'var(--danger)'};
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        z-index: 9999;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        animation: slideUp 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideDown 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add CSS animations dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes slideUp {
        from { transform: translateX(-50%) translateY(20px); opacity: 0; }
        to { transform: translateX(-50%) translateY(0); opacity: 1; }
    }
    @keyframes slideDown {
        from { transform: translateX(-50%) translateY(0); opacity: 1; }
        to { transform: translateX(-50%) translateY(20px); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Handle window resize for responsive sidebar
window.addEventListener('resize', function() {
    const sidebar = document.querySelector('.sidebar');
    if (window.innerWidth > 768 && sidebar) {
        sidebar.classList.remove('open');
    }
});

/* ===== REMINDER SOUND PLAYBACK ===== */

// Default beep sound generated with Web Audio API
function playDefaultBeep() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioContext();
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();

        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);

        oscillator.connect(gain);
        gain.connect(ctx.destination);

        oscillator.start();
        oscillator.stop(ctx.currentTime + 0.6);
    } catch (e) {
        console.log('Could not play default beep:', e);
    }
}

// Play a reminder sound (custom file or default beep)
function playReminderSound(filePath) {
    if (filePath) {
        try {
            const audio = new Audio(filePath);
            audio.volume = 0.8;
            audio.play().catch(() => playDefaultBeep());
        } catch (e) {
            playDefaultBeep();
        }
    } else {
        playDefaultBeep();
    }
}

// Check for due reminders on page load and every 30 seconds
function checkDueReminders() {
    // This is checked via server-side route; see app.py
}

// Periodic reminder checker
setInterval(() => {
    fetch('/api/check-reminders', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.due && data.due.length > 0) {
                data.due.forEach(task => {
                    showToast(`⏰ Reminder: ${task.title}`, 'success');
                    playReminderSound(task.reminder_sound);
                });
            }
        })
        .catch(() => {});
}, 30000);

// Check immediately on load
setTimeout(() => {
    fetch('/api/check-reminders', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.due && data.due.length > 0) {
                data.due.forEach(task => {
                    showToast(`⏰ Reminder: ${task.title}`, 'success');
                    playReminderSound(task.reminder_sound);
                });
            }
        })
        .catch(() => {});
}, 5000);
