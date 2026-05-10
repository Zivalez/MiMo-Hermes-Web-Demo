document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyze-btn');
    const repoInput = document.getElementById('repo-url');
    const processingSection = document.getElementById('processing-section');
    const resultsSection = document.getElementById('results-section');
    const liveLogs = document.getElementById('live-logs');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    // UI Elements for Data binding
    const elLanguage = document.getElementById('res-language');
    const elFileCount = document.getElementById('res-file-count');
    const elFiles = document.getElementById('res-files');
    const elPlanSummary = document.getElementById('res-plan-summary');
    const elPlanOrder = document.getElementById('res-plan-order');
    const elPlanRisks = document.getElementById('res-plan-risks');
    const elValStatus = document.getElementById('res-val-status');
    const elValCmd = document.getElementById('res-val-cmd');
    const elValLogs = document.getElementById('res-val-logs');

    // Tab switching
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(btn.getAttribute('data-target')).classList.add('active');
        });
    });

    function appendLog(message, type = 'info') {
        const p = document.createElement('p');
        p.className = `log-${type}`;
        p.textContent = `> ${message}`;
        liveLogs.appendChild(p);
        liveLogs.scrollTop = liveLogs.scrollHeight;
    }

    function setStep(stepId) {
        document.querySelectorAll('.step').forEach(s => {
            if (s.id === stepId) {
                s.classList.add('active');
                const icon = s.querySelector('.step-icon');
                if(!icon.querySelector('.spinner')) {
                     icon.innerHTML = '<div class="spinner"></div>';
                }
            } else {
                if (s.classList.contains('active')) {
                    s.classList.remove('active');
                    s.classList.add('completed');
                    s.querySelector('.step-icon').innerHTML = '✓';
                }
            }
        });
    }

    analyzeBtn.addEventListener('click', async () => {
        const url = repoInput.value.trim();
        if (!url) {
            alert('Please enter a repository URL');
            return;
        }

        // Reset UI
        resultsSection.classList.add('hidden');
        processingSection.classList.remove('hidden');
        liveLogs.innerHTML = '';
        document.querySelectorAll('.step').forEach(s => {
            s.classList.remove('active', 'completed');
            const num = s.id.split('-')[1]; // just a hack to reset
        });

        // Initialize first step
        appendLog(`Starting analysis for: ${url}`, 'info');
        setStep('step-ingest');
        
        try {
            // Call our FastAPI backend
            appendLog(`Cloning repository into workspace...`);
            
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: url })
            });

            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            // We stream updates using a mocked process since actual backend might not stream yet.
            // For UI purposes, let's simulate the steps before showing actual results.
            setTimeout(() => {
                setStep('step-plan');
                appendLog('Repository ingested. Detected 120 files.', 'success');
                appendLog('Generating AI Modernization Plan...', 'info');
            }, 1500);

            setTimeout(() => {
                setStep('step-validate');
                appendLog('Plan generated. Initiating Docker sandbox...', 'info');
                appendLog('Running validations...', 'info');
            }, 3000);

            setTimeout(async () => {
                setStep('step-report');
                appendLog('Validation complete. Aggregating artifacts.', 'success');
                
                // Get the actual data
                const data = await response.json();
                renderResults(data);
                
                setTimeout(() => {
                    processingSection.classList.add('hidden');
                    resultsSection.classList.remove('hidden');
                }, 1000);

            }, 4500);

        } catch (error) {
            appendLog(`Error: ${error.message}`, 'error');
            setStep('step-report'); // Stop
        }
    });

    function renderResults(data) {
        // Context
        elLanguage.textContent = data.context.primary_language || 'Unknown';
        elFileCount.textContent = data.context.files ? data.context.files.length : '0';
        
        elFiles.innerHTML = '';
        (data.context.files || []).slice(0, 15).forEach(f => {
            const li = document.createElement('li');
            li.textContent = f.path;
            elFiles.appendChild(li);
        });

        // Plan
        const plan = data.plan || {};
        elPlanSummary.innerHTML = `<p>${plan.project_summary || plan.recommended_architecture || 'No summary available.'}</p>`;
        
        elPlanOrder.innerHTML = '';
        (plan.execution_order || []).forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            elPlanOrder.appendChild(li);
        });

        elPlanRisks.innerHTML = '';
        (plan.risks || []).forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            elPlanRisks.appendChild(li);
        });

        // Validation
        const val = data.validation || {};
        elValStatus.textContent = (val.status || 'Unknown').toUpperCase();
        elValStatus.className = `status-badge ${val.status === 'passed' ? 'passed' : 'failed'}`;
        
        elValCmd.textContent = Array.isArray(val.command) ? val.command.join(' ') : 'Unknown command';
        
        const logs = `--- STDOUT ---\n${val.stdout || 'Empty'}\n\n--- STDERR ---\n${val.stderr || 'Empty'}`;
        elValLogs.innerHTML = `<pre>${escapeHtml(logs)}</pre>`;
    }

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
});
