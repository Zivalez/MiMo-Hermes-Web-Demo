document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyze-btn');
    const repoInput = document.getElementById('repo-url');
    const processingSection = document.getElementById('processing-section');
    const resultsSection = document.getElementById('results-section');
    const liveLogs = document.getElementById('live-logs');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const modelSelect = document.getElementById('model-select');
    const maxFilesSegments = document.querySelectorAll('#max-files-toggle .segment');

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
    const planModelBadge = document.getElementById('plan-model-badge');
    let activeModel = 'mimo-v2.5-pro';

    // Segmented control toggle
    maxFilesSegments.forEach(btn => {
        btn.addEventListener('click', () => {
            maxFilesSegments.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // Custom dropdown
    if (modelSelect) {
        const trigger = modelSelect.querySelector('.select-trigger');
        const menu = modelSelect.querySelector('.select-menu');
        const options = modelSelect.querySelectorAll('.select-option');
        const valueLabel = trigger.querySelector('.select-value');

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.custom-select.open').forEach(el => {
                if (el !== modelSelect) el.classList.remove('open');
            });
            modelSelect.classList.toggle('open');
        });

        options.forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                options.forEach(o => o.classList.remove('active'));
                opt.classList.add('active');
                trigger.dataset.value = opt.dataset.value;
                valueLabel.textContent = opt.textContent;
                modelSelect.classList.remove('open');
            });
        });

        document.addEventListener('click', () => {
            modelSelect.classList.remove('open');
        });
    }

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
                s.classList.remove('completed');
                const icon = s.querySelector('.step-icon');
                if(!icon.querySelector('.spinner')) {
                     icon.innerHTML = '<div class="spinner"></div>';
                }
            } else {
                if (s.classList.contains('active')) {
                    s.classList.remove('active');
                    s.classList.add('completed');
                    s.querySelector('.step-icon').innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
                }
            }
        });
    }

    async function handleAnalyze() {
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
            appendLog('Connecting to pipeline...');
            
            // Live ticker shown while backend is processing (actual fetch is awaited below)
            const phases = [
                { step: 'step-ingest', messages: [
                    'Cloning repository into workspace...',
                    'Resolving Git objects and refs...',
                    'Reading file tree and detecting language...',
                    'Extracting source file snapshots...',
                    'Building repository context manifest...',
                ]},
                { step: 'step-plan', messages: [
                    'Sending context to MiMo AI model...',
                    'AI is analyzing architecture patterns...',
                    'Generating modernization strategies...',
                    'Evaluating risk factors and execution order...',
                    'Finalizing structured plan JSON...',
                ]},
                { step: 'step-validate', messages: [
                    'Spinning up sandbox environment...',
                    'Installing project dependencies...',
                    'Running test suite in isolated container...',
                    'Collecting stdout / stderr output...',
                    'Writing validation report...',
                ]},
            ];

            let phaseIdx = 0;
            let msgIdx = 0;
            setStep(phases[0].step);
            appendLog(phases[0].messages[0]);

            const ticker = setInterval(() => {
                msgIdx++;
                const phase = phases[phaseIdx];
                if (msgIdx < phase.messages.length) {
                    appendLog(phase.messages[msgIdx]);
                } else {
                    phaseIdx++;
                    msgIdx = 0;
                    if (phaseIdx < phases.length) {
                        setStep(phases[phaseIdx].step);
                        appendLog(phases[phaseIdx].messages[0]);
                    }
                }
            }, 4000);

            activeModel = modelSelect ? modelSelect.querySelector('.select-trigger').dataset.value : 'mimo-v2.5-pro';
            const selectedMaxFiles = document.querySelector('#max-files-toggle .segment.active')?.dataset.value || '100';

            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repo_url: url, model: activeModel, max_files: parseInt(selectedMaxFiles, 10) })
            });

            clearInterval(ticker);

            if (!response.ok) {
                let detail = `Server responded with ${response.status}`;
                try {
                    const errBody = await response.json();
                    if (errBody?.detail) detail = errBody.detail;
                } catch (_) {}
                throw new Error(detail);
            }

            const data = await response.json();
            const fileCount = data.context?.files?.length ?? '?';

            // Mark remaining steps as completed in sequence
            setStep('step-plan');
            appendLog(`Repository ingested. Detected ${fileCount} file(s).`, 'success');
            setStep('step-validate');
            appendLog('AI Modernization Plan generated.', 'success');
            setStep('step-report');
            appendLog('Sandbox validation complete.', 'success');
            appendLog('Aggregating artifacts...', 'info');

            renderResults(data);
            setTimeout(() => {
                setStep('done');
                resultsSection.classList.remove('hidden');
            }, 800);

        } catch (error) {
            let msg = error.message;
            try {
                const errData = await error.response?.json();
                if (errData?.detail) msg = errData.detail;
            } catch (_) {}
            appendLog(`Error: ${msg}`, 'error');
            document.querySelectorAll('.step').forEach(s => {
                if (s.classList.contains('active')) {
                    s.querySelector('.step-icon').innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" stroke="var(--accent-red)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
                }
            });
        }
    }

    analyzeBtn.addEventListener('click', handleAnalyze);
    repoInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleAnalyze();
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
        // Plan (Dynamic Recursive Rendering)
        if (planModelBadge) {
            planModelBadge.textContent = `Generated by ${activeModel.replace(/-/g, ' ').toUpperCase()}`;
        }
        const plan = data.plan || {};
        const planContainer = document.getElementById('dynamic-plan-container');
        planContainer.innerHTML = '';
        
        function formatKey(key) {
            if (!key) return '';
            return key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        }
        
        function buildNode(key, value) {
            const wrapper = document.createElement('div');
            wrapper.className = 'json-node';
            
            if (typeof value === 'object' && value !== null) {
                if (key) {
                    const title = document.createElement('h4');
                    title.className = 'json-key';
                    title.textContent = formatKey(key);
                    wrapper.appendChild(title);
                }
                
                const children = document.createElement('div');
                children.className = 'json-children';
                
                if (Array.isArray(value)) {
                    const ul = document.createElement('ul');
                    value.forEach(item => {
                        const li = document.createElement('li');
                        if (typeof item === 'object' && item !== null) {
                            li.className = 'has-card';
                            const card = document.createElement('div');
                            card.className = 'json-node json-card';
                            for (const k in item) {
                                const v = item[k];
                                if (typeof v === 'object' && v !== null) {
                                    card.appendChild(buildNode(k, v));
                                } else {
                                    const line = document.createElement('div');
                                    line.className = 'json-line';
                                    line.innerHTML = `<span class="json-key">${formatKey(k)}:</span> <span class="json-value">${escapeHtml(String(v)).replace(/\n/g, '<br>')}</span>`;
                                    card.appendChild(line);
                                }
                            }
                            li.appendChild(card);
                        } else {
                            li.innerHTML = escapeHtml(String(item)).replace(/\n/g, '<br>');
                        }
                        ul.appendChild(li);
                    });
                    children.appendChild(ul);
                } else {
                    for (const k in value) {
                        children.appendChild(buildNode(k, value[k]));
                    }
                }
                wrapper.appendChild(children);
            } else {
                if (key) {
                    wrapper.innerHTML = `<span class="json-key">${formatKey(key)}:</span> <span class="json-value">${escapeHtml(String(value)).replace(/\n/g, '<br>')}</span>`;
                } else {
                    wrapper.innerHTML = `<span class="json-value">${escapeHtml(String(value)).replace(/\n/g, '<br>')}</span>`;
                }
            }
            return wrapper;
        }
        
        if (Object.keys(plan).length === 0) {
            planContainer.innerHTML = '<p>No plan data available.</p>';
        } else {
            for (const key in plan) {
                planContainer.appendChild(buildNode(key, plan[key]));
            }
        }

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