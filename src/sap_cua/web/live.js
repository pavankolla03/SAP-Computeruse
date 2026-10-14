'use strict';
(() => {
  const el = id => document.getElementById(id);
  const make = (tag, text, cls) => {
    const item = document.createElement(tag); item.textContent = text;
    if (cls) item.className = cls;
    return item;
  };
  let revision = 0, reviewedPlan = null, templates = [], selectedRun = null;
  let connectionRevision = null, activeRun = null, pollTimer = null, pollRevision = 0;
  let preparing = false, submitting = false, savingProfile = false;
  const terminal = new Set(['succeeded', 'failed', 'cancelled', 'interrupted']);
  const isRunning = run => run && ['running', 'cancelling'].includes(run.status);
  const secretFields = ['sap-client-id', 'sap-client-secret', 'sap-runtime-client-id', 'sap-runtime-client-secret'];
  const profileFields = {
    api_base: 'sap-api-base', token_url: 'sap-token-url', runtime_base: 'sap-runtime-base',
    runtime_token_url: 'sap-runtime-token-url', allowed_test_prefix: 'sap-test-prefix'
  };
  const errorText = data => {
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) return 'Check these fields: ' + [...new Set(data.detail.map(x => (x.loc || []).filter(y => y !== 'body').join('.')))].join(', ');
    return 'The service could not complete this request. Check the form and try again.';
  };
  async function call(base, path, body) {
    const multipart = body instanceof FormData;
    const response = await fetch(base + path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: {'X-SAP-CUA': 'workbench', ...(multipart ? {} : {'Content-Type': 'application/json'})},
      body: body === undefined ? undefined : multipart ? body : JSON.stringify(body)
    });
    let data;
    try { data = await response.json(); } catch { throw Error('The service returned an unreadable response. Inspect history before retrying a write.'); }
    if (!response.ok) throw Error(errorText(data));
    return data;
  }
  const live = (path, body) => call('/api/live', path, body);
  const sap = (path, body) => call('/api/sap', path, body);
  function changedControl(event) { if (event.target.tagName === 'SELECT' || ['checkbox', 'file'].includes(event.target.type)) clearReview(); }
  function notice(id, text, failed = false) { el(id).textContent = text; el(id).classList.toggle('failed', failed); }
  function clearReview(text = 'Configuration changed. Prepare a new deployment review.') {
    revision++; reviewedPlan = null; el('live-execute').disabled = true;
    el('live-plan-download').hidden = true; el('live-plan-badge').textContent = 'REVIEW REQUIRED';
    notice('live-review-note', text);
  }
  function syncControls() {
    const busy = Boolean(activeRun) || submitting;
    el('live-execute').disabled = busy || savingProfile || !reviewedPlan || Boolean(reviewedPlan.blockers?.length);
    el('live-prepare-plan').disabled = busy || savingProfile || preparing || !el('live-template-select').value;
    el('live-import-template').disabled = busy;
    el('sap-save-profile').disabled = busy || savingProfile;
    el('sap-clear-profile').disabled = busy || savingProfile;
    for (const field of el('sap-profile-form').elements) field.disabled = busy || savingProfile;
    el('live-cancel').disabled = !isRunning(selectedRun) || selectedRun.cancel_requested === true || selectedRun.cancellation_requested === true;
    el('live-refresh-run').disabled = !selectedRun;
  }
  function showReadiness(status) {
    if (connectionRevision !== null && status.connection_revision !== connectionRevision) clearReview('Connection changed. Prepare a new deployment review.');
    connectionRevision = status.connection_revision;
    activeRun = status.active_run_id || null;
    el('live-badge').textContent = activeRun ? 'RUN IN PROGRESS' : status.execution_enabled ? 'DEV CONNECTION READY' : 'SETUP REQUIRED';
    notice('live-readiness-message', activeRun ? 'A DEV run is active. Its actions can be observed below.' : status.execution_enabled ? 'Connection configured for reviewed DEV execution. SAP acceptance and functional behavior are checked during each run.' : 'Complete the prerequisites below. You can prepare and inspect your artifact before running.');
    el('live-blockers').replaceChildren();
    for (const blocker of status.blockers || []) el('live-blockers').append(make('li', blocker));
    syncControls();
    return status;
  }
  async function refreshReadiness() { return showReadiness(await live('/status')); }
  function showProfile(status, fill = false) {
    const profile = status.profile || status;
    if (fill) {
      for (const [key, id] of Object.entries(profileFields)) el(id).value = profile[key] || (key === 'allowed_test_prefix' ? '/http/' : '');
      el('sap-allow-dev-writes').checked = profile.allow_dev_writes === true;
    }
    el('sap-badge').textContent = status.configured ? 'CONFIGURED' : 'SETUP REQUIRED';
    el('sap-probe').disabled = !status.configured;
    notice('sap-setup', status.configured ? 'Configured API host: ' + status.tenant_host + '. Check read access before deploying.' : 'Enter your DEV management API connection. Credential fields are never returned by the server.');
    const probe = status.last_probe || status;
    el('sap-checks').replaceChildren();
    for (const check of probe.checks || []) el('sap-checks').append(make('div', check.resource + ' · ' + (check.success ? 'read access confirmed' : check.reason) + (check.status_code ? ' · HTTP ' + check.status_code : ''), 'connection-check'));
    if (probe.success === true && probe.checks?.length) el('sap-badge').textContent = 'READ ACCESS CONFIRMED';
    if (profile.client_secret_present || profile.runtime_client_secret_present) notice('sap-profile-message', 'Credentials are available. Leave credential fields blank to retain this connection’s saved values.');
    syncControls();
  }
  el('sap-profile-form').addEventListener('input', () => clearReview());
  el('sap-profile-form').addEventListener('change', changedControl);
  el('sap-profile-form').addEventListener('submit', async event => {
    event.preventDefault(); if (savingProfile || activeRun) return;
    savingProfile = true; clearReview(); syncControls();
    const payload = {environment: 'dev', allow_dev_writes: el('sap-allow-dev-writes').checked};
    for (const [key, id] of Object.entries(profileFields)) payload[key] = el(id).value.trim();
    for (const [key, id] of Object.entries({client_id: 'sap-client-id', client_secret: 'sap-client-secret', runtime_client_id: 'sap-runtime-client-id', runtime_client_secret: 'sap-runtime-client-secret'})) payload[key] = el(id).value;
    notice('sap-profile-message', 'Saving session connection…');
    try {
      showProfile(await sap('/profile', payload), true);
      for (const id of secretFields) el(id).value = '';
      notice('sap-profile-message', 'Session connection saved. Credentials are held in server memory and are not stored in this browser.');
      await refreshReadiness();
    } catch (error) { notice('sap-profile-message', error.message, true); }
    finally { savingProfile = false; syncControls(); }
  });
  el('sap-clear-profile').addEventListener('click', async () => {
    if (savingProfile || activeRun) return;
    savingProfile = true; clearReview('Connection forgotten. Configure SAP DEV before preparing another run.'); syncControls();
    try {
      showProfile(await sap('/profile/clear', {}), true);
      for (const id of secretFields) el(id).value = '';
      notice('sap-profile-message', 'Session credentials forgotten.'); await refreshReadiness();
    } catch (error) { notice('sap-profile-message', error.message, true); }
    finally { savingProfile = false; syncControls(); }
  });
  el('sap-probe').addEventListener('click', async () => {
    el('sap-probe').disabled = true; notice('sap-setup', 'Checking read access…');
    try { showProfile(await sap('/probe', {})); await refreshReadiness(); }
    catch (error) { notice('sap-setup', error.message, true); sap('/profile').then(s => { el('sap-probe').disabled = !s.configured; }).catch(() => {}); }
  });
  function selectedTemplate() { return templates.find(item => item.id === el('live-template-select').value); }
  function showTemplate(prefillIdentity = false) {
    const template = selectedTemplate(); el('live-template-info').replaceChildren(); el('live-parameters').replaceChildren();
    el('live-template-download').hidden = !template;
    if (!template) { syncControls(); return; }
    el('live-template-download').href = '/api/live/templates/' + encodeURIComponent(template.id) + '/artifact';
    el('live-template-info').append(make('p', template.title), make('small', 'Approved SHA-256: ' + template.sha256));
    if (template.artifact_id) {
      el('live-template-info').append(make('p', 'SAP artifact identity: ' + template.artifact_id + '. This identity is preserved; an existing iFlow with this ID cannot be overwritten.'));
      if (prefillIdentity) el('live-iflow-id').value = template.artifact_id;
    }
    const parameters = template.parameters || [];
    if (parameters.length) {
      el('live-parameters').append(make('h3', 'Template parameters'), make('p', 'Values replace the approved template’s {{PARAM}} placeholders. Use credential aliases rather than secrets.'));
      for (const parameter of parameters) {
        const name = typeof parameter === 'string' ? parameter : parameter.name;
        const label = make('label', name), input = document.createElement('input');
        input.id = 'live-param-' + name; input.dataset.parameter = name; input.required = true; input.maxLength = 4000;
        label.htmlFor = input.id; el('live-parameters').append(label, input);
      }
    } else el('live-parameters').append(make('p', 'No {{PARAM}} placeholders were found. This export will retain its existing adapter configuration. Review that configuration before deployment.'));
    syncControls();
  }
  async function refreshTemplates(preferred) {
    const previous = el('live-template-select').value;
    templates = await live('/templates');
    el('live-template-select').replaceChildren(new Option('Select a template…', ''));
    for (const template of templates) el('live-template-select').append(new Option(template.title, template.id));
    el('live-template-select').value = preferred || previous;
    if (!el('live-template-select').value && templates.length === 1) el('live-template-select').value = templates[0].id;
    clearReview('Select and configure an imported iFlow, then prepare a deployment review.'); showTemplate(true);
  }
  el('live-template-select').addEventListener('change', () => { clearReview(); showTemplate(true); });
  el('live-refresh-templates').addEventListener('click', () => refreshTemplates().catch(error => notice('live-import-message', error.message, true)));
  el('live-template-form').addEventListener('input', () => clearReview());
  el('live-template-form').addEventListener('change', changedControl);
  el('live-template-form').addEventListener('submit', async event => {
    event.preventDefault(); if (activeRun) return;
    const file = el('live-template-file').files[0];
    if (!file || file.size > 20000000) { notice('live-import-message', 'Choose an exported ZIP no larger than 20 MB.', true); return; }
    const body = new FormData(); body.append('file', file); body.append('title', el('live-template-title').value.trim()); body.append('approved', String(el('live-template-approved').checked));
    el('live-import-template').disabled = true; notice('live-import-message', 'Validating and importing approved artifact…'); clearReview();
    try {
      const result = await live('/templates', body); await refreshTemplates(result.id);
      notice('live-import-message', 'Approved artifact imported. Configure its parameters and test contract.');
      el('live-template-file').value = ''; el('live-template-approved').checked = false;
    } catch (error) { notice('live-import-message', error.message, true); }
    finally { syncControls(); }
  });
  el('live-plan-form').addEventListener('input', () => clearReview());
  el('live-plan-form').addEventListener('change', changedControl);
  function showPlan(plan, runnable = true) {
    reviewedPlan = runnable ? plan : null;
    el('live-plan-json').textContent = JSON.stringify(plan, null, 2);
    el('live-plan-badge').textContent = !runnable ? 'EXECUTED · VIEW ONLY' : plan.blockers?.length ? 'BLOCKED' : 'REVIEW READY';
    notice('live-review-note', runnable ? 'Review the resource IDs, test contract, actions, and exact artifact below. Any configuration edit requires a new review.' : 'This is the immutable plan associated with the selected run. It cannot be replayed.');
    el('live-review-summary').replaceChildren();
    for (const [label, value] of Object.entries({Template: plan.template_title || plan.template_id, Package: plan.package_id, iFlow: plan.iflow_id, 'Artifact SHA-256': plan.artifact_sha256, 'Test endpoint': plan.test?.path, 'Expected response': `${plan.test?.expected_status || ''} · ${plan.test?.response_contains || ''}`})) el('live-review-summary').append(make('dt', label), make('dd', String(value ?? '')));
    el('live-plan-steps').replaceChildren();
    for (const step of plan.steps || []) el('live-plan-steps').append(make('div', `${step.id || ''}  ${step.action || step.stage || ''}`, 'plan-step'));
    el('live-plan-blockers').replaceChildren();
    for (const blocker of plan.blockers || []) el('live-plan-blockers').append(make('li', blocker, 'failed'));
    el('live-plan-download').href = '/api/live/plans/' + encodeURIComponent(plan.id) + '/artifact'; el('live-plan-download').hidden = false;
    syncControls();
  }
  el('live-plan-form').addEventListener('submit', async event => {
    event.preventDefault(); if (preparing || activeRun) return;
    const template = selectedTemplate(); if (!template) { notice('live-plan-message', 'Import and select an approved iFlow first.', true); return; }
    clearReview('Preparing immutable deployment review…'); const ticket = revision;
    preparing = true; syncControls(); notice('live-plan-message', 'Validating artifact parameters and functional-test contract…');
    const parameters = {};
    for (const input of el('live-parameters').querySelectorAll('[data-parameter]')) parameters[input.dataset.parameter] = input.value;
    const payload = {template_id: template.id, parameters, package_id: el('live-package-id').value.trim(), iflow_id: el('live-iflow-id').value.trim(), name: el('live-iflow-name').value.trim(), test: {path: el('live-test-path').value.trim(), method: 'POST', content_type: el('live-test-content-type').value, body: el('live-test-body').value, expected_status: Number(el('live-test-status').value), response_contains: el('live-test-response').value}};
    try {
      const plan = await live('/plans', payload);
      if (ticket !== revision) { notice('live-plan-message', 'Configuration changed while preparing. Generate a new review.'); return; }
      showPlan(plan); notice('live-plan-message', plan.blockers?.length ? 'Review created with unmet prerequisites.' : 'Deployment review ready. No SAP resources have been changed.');
    } catch (error) { if (ticket === revision) notice('live-plan-message', error.message, true); }
    finally { preparing = false; syncControls(); }
  });
  function rememberRun(id) { try { sessionStorage.setItem('sap-live-selected-run', id); } catch {} }
  function readRememberedRun() { try { return sessionStorage.getItem('sap-live-selected-run'); } catch { return null; } }
  function showRun(run) {
    selectedRun = run; rememberRun(run.id);
    el('live-run-badge').textContent = String(run.status).toUpperCase();
    el('live-run-json').textContent = JSON.stringify(run, null, 2);
    el('live-run-export').href = '/api/live/runs/' + encodeURIComponent(run.id) + '/export'; el('live-run-export').hidden = false;
    el('live-run-steps').replaceChildren();
    for (const [index, step] of (run.steps || []).entries()) {
      const item = make('div', '', 'step'), body = make('div', '');
      item.append(make('b', String(index + 1).padStart(2, '0')), body);
      body.append(make('strong', step.stage || step.action?.action || step.action || 'Action'));
      body.append(make('small', `${step.status || ''}${step.verification ? ' · ' + (step.verification.success ? 'verified' : 'verification incomplete') : ''}`));
      if (step.result?.reason) body.append(make('small', step.result.reason));
      el('live-run-steps').append(item);
    }
    const descriptions = {planned: 'Saved deployment plan. Review the configuration and artifact before running.', succeeded: 'SAP deployment and the configured functional test were verified. Inspect evidence for the precise checks.', failed: 'Run stopped after a failed action or verification. Review evidence before making another attempt.', cancelled: 'Run stopped. Previously completed SAP changes remain.', interrupted: 'Execution was interrupted. Existing actions will not be replayed.', running: 'Executing the reviewed plan. SAP actions are recorded as they complete.', cancelling: 'Stop requested. Waiting for the current action to finish.'};
    notice('live-run-message', run.error ? `${descriptions[run.status] || ''} ${typeof run.error === 'string' ? run.error : 'See evidence for error details.'}` : descriptions[run.status] || 'Waiting for execution status…', run.status === 'failed' || run.status === 'interrupted');
    if (isRunning(run) && (run.cancel_requested || run.cancellation_requested)) notice('live-run-message', 'Stop requested. The current action may still finish; no automatic rollback is performed.');
    syncControls();
  }
  function restorePlanInputs(plan) {
    el('live-template-select').value = plan.template_id; showTemplate();
    for (const input of el('live-parameters').querySelectorAll('[data-parameter]')) input.value = plan.parameters?.[input.dataset.parameter] || '';
    for (const [id, value] of Object.entries({'live-package-id': plan.package_id, 'live-iflow-id': plan.iflow_id, 'live-iflow-name': plan.name, 'live-test-path': plan.test?.path, 'live-test-body': plan.test?.body, 'live-test-status': plan.test?.expected_status, 'live-test-response': plan.test?.response_contains, 'live-test-content-type': plan.test?.content_type || 'application/json'})) el(id).value = value ?? '';
  }
  function stopPolling() { if (pollTimer) clearTimeout(pollTimer); pollTimer = null; pollRevision++; }
  async function openRun(id, displayPlan = true) {
    stopPolling(); const ticket = pollRevision;
    clearReview('Inspecting recorded DEV execution. Completed actions cannot be replayed.');
    const reviewTicket = revision;
    try {
      const run = await live('/runs/' + encodeURIComponent(id));
      if (ticket !== pollRevision) return;
      showRun(run);
      if (displayPlan && run.plan) {
        if (run.status === 'planned' && reviewTicket === revision && run.plan.connection_revision === connectionRevision && !activeRun) {
          restorePlanInputs(run.plan); showPlan(run.plan, true);
        } else {
          showPlan(run.plan, false);
          if (run.status === 'planned') { el('live-plan-badge').textContent = 'NEW REVIEW REQUIRED'; notice('live-review-note', 'This saved plan cannot run with the current connection or while another run is active. Prepare a new review when ready.'); }
        }
      }
      if (isRunning(run)) { activeRun = run.id; pollTimer = setTimeout(() => pollRun(id, ticket), 2000); }
      else if (terminal.has(run.status)) {
        if (activeRun === run.id) activeRun = null;
        await Promise.allSettled([refreshReadiness(), refreshHistory()]);
      }
      syncControls();
    } catch (error) { if (ticket === pollRevision) notice('live-run-message', error.message, true); }
  }
  async function pollRun(id, ticket) {
    try {
      const run = await live('/runs/' + encodeURIComponent(id));
      if (ticket !== pollRevision) return;
      showRun(run);
      if (isRunning(run)) pollTimer = setTimeout(() => pollRun(id, ticket), 2000);
      else { if (activeRun === id) activeRun = null; syncControls(); await Promise.allSettled([refreshReadiness(), refreshHistory()]); }
    } catch (error) {
      if (ticket !== pollRevision) return;
      notice('live-run-message', 'Status temporarily unavailable. No action will be replayed. ' + error.message, true);
      pollTimer = setTimeout(() => pollRun(id, ticket), 5000);
    }
  }
  el('live-execute').addEventListener('click', async () => {
    if (!reviewedPlan || submitting || activeRun || reviewedPlan.blockers?.length) return;
    const plan = reviewedPlan; submitting = true; clearReview('Execution requested. Check run evidence for progress.'); syncControls();
    notice('live-run-message', 'Starting the reviewed DEV plan…');
    try {
      const run = await live('/plans/' + encodeURIComponent(plan.id) + '/run', {});
      activeRun = run.id; await openRun(run.id); await refreshHistory();
    } catch (error) {
      notice('live-run-message', error.message + ' Inspect DEV history before preparing another run.', true);
      const status = await refreshReadiness().catch(() => null);
      if (status?.active_run_id) await openRun(status.active_run_id);
      await refreshHistory().catch(() => {});
    } finally { submitting = false; syncControls(); }
  });
  el('live-cancel').addEventListener('click', async () => {
    if (!isRunning(selectedRun)) return;
    el('live-cancel').disabled = true;
    try { await live('/runs/' + encodeURIComponent(selectedRun.id) + '/cancel', {}); notice('live-run-message', 'Stop requested. Waiting for the current action to finish.'); await openRun(selectedRun.id); }
    catch (error) { notice('live-run-message', error.message, true); syncControls(); }
  });
  el('live-refresh-run').addEventListener('click', () => { if (selectedRun) openRun(selectedRun.id); });
  async function refreshHistory() {
    const runs = await live('/runs'); el('live-history').replaceChildren();
    if (!runs.length) { el('live-history').append(make('p', 'No DEV deployments yet.')); return; }
    for (const run of runs) {
      const row = make('div', '', 'history-row');
      row.append(make('span', run.plan?.name || run.plan?.iflow_id || run.name || run.id), make('small', run.status));
      const button = make('button', run.status === 'planned' ? 'Open plan' : 'Inspect', 'secondary'); button.addEventListener('click', () => openRun(run.id)); row.append(button); el('live-history').append(row);
    }
  }
  el('live-refresh-history').addEventListener('click', () => refreshHistory().catch(error => notice('live-run-message', error.message, true)));
  async function init() {
    const result = await Promise.allSettled([
      sap('/profile').then(s => showProfile(s, true)).catch(error => notice('sap-profile-message', error.message, true)),
      refreshReadiness().catch(error => { notice('live-readiness-message', error.message, true); el('live-badge').textContent = 'UNAVAILABLE'; return null; }),
      refreshTemplates().catch(error => notice('live-import-message', error.message, true)),
      refreshHistory().catch(error => notice('live-run-message', error.message, true))
    ]);
    const status = result[1].status === 'fulfilled' ? result[1].value : null;
    const id = status?.active_run_id || readRememberedRun();
    if (id) await openRun(id);
    syncControls();
  }
  init();
})();
