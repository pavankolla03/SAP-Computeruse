'use strict';
const $ = id => document.getElementById(id);
let currentPlan = null;
let revision = 0;
let executing = false;
function node(tag, text, cls) {
  const e = document.createElement(tag); e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
async function request(base, path, body) {
  const response = await fetch(base + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'Content-Type': 'application/json', 'X-SAP-CUA': 'workbench'},
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  let result;
  try { result = await response.json(); }
  catch { throw Error('The service could not complete the request. Refresh and try again.'); }
  if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Check the form fields and try again.');
  return result;
}
const api = (path, body) => request('/api/rag', path, body);
const sapApi = (path, body) => request('/api/sap', path, body);
function message(text, error = false) { $('message').textContent = text; $('message').className = error ? 'failed' : ''; }
function showSources(hits) {
  $('sources').replaceChildren();
  if (!hits.length) { $('sources').append(node('p', 'No matching knowledge.')); return; }
  for (const hit of hits) {
    const card = node('article', '', 'source-card');
    card.append(node('strong', hit.title), node('p', hit.content), node('small', `${hit.collection} · ${hit.source} · ${hit.source_version} · score ${Number(hit.rerank_score).toFixed(2)}`));
    $('sources').append(card);
  }
}
function invalidatePlan() {
  revision++; currentPlan = null; $('execute').disabled = true;
  $('plan-note').textContent = 'Generate a new plan for this requirement.';
}
function showPlan(plan, runnable = true) {
  currentPlan = runnable ? plan : null;
  $('plan-json').textContent = JSON.stringify(plan, null, 2);
  $('plan-summary').replaceChildren();
  for (const step of plan.steps) $('plan-summary').append(node('div', `${step.id}  ${step.action}  → ${step.preferred_executor}`, 'plan-step'));
  for (const blocker of plan.blockers) $('plan-summary').append(node('p', blocker, 'failed'));
  $('execute').disabled = !runnable || executing || plan.blockers.length > 0;
  $('plan-note').textContent = `${plan.steps.length} actions · ${plan.sources.length} retrieved sources${runnable ? '' : ' · view only'}`;
  showSources(plan.sources);
}
function showRun(run) {
  $('result-badge').textContent = run.status.toUpperCase(); $('trace').replaceChildren();
  for (const [i, step] of (run.steps || []).entries()) {
    const row = node('div', '', 'step'); const body = node('div', '');
    row.append(node('b', String(i + 1).padStart(2, '0')), body);
    body.append(node('strong', step.action.action), node('small', `${step.executor} · ${step.verification.success ? 'verified' : 'failed'}${step.recovery?.length ? ' · recovered after ' + step.recovery.length + ' attempt(s)' : ''}`));
    $('trace').append(row);
  }
  if (!run.steps?.length) $('trace').append(node('p', run.status === 'planned' ? 'Saved plan. Review its actions before execution.' : 'No executed steps recorded.'));
  $('evidence').textContent = JSON.stringify(run, null, 2);
  $('export-run').href = '/api/rag/runs/' + encodeURIComponent(run.id) + '/export'; $('export-run').hidden = false;
  if (run.error) $('trace').append(node('p', run.error, 'failed'));
}
async function openRun(id) {
  if (executing) return;
  invalidatePlan(); const ticket = revision;
  try {
    const run = await api('/runs/' + encodeURIComponent(id));
    if (ticket !== revision) return;
    $('requirement').value = run.instruction;
    if (run.plan) showPlan(run.plan, run.status === 'planned');
    else { $('plan-json').textContent = 'This older run has no saved semantic plan.'; $('plan-summary').replaceChildren(); }
    showRun(run); message(run.status === 'planned' ? 'Saved plan restored. Review it before running.' : 'Run opened. Completed actions cannot be replayed.');
  } catch (e) { if (ticket === revision) message(e.message, true); }
}
async function refresh() {
  const runs = await api('/runs'); $('history').replaceChildren();
  if (!runs.length) $('history').append(node('p', 'No runs yet.'));
  for (const run of runs) {
    const row = node('div', '', 'history-row');
    row.append(node('span', run.instruction), node('small', run.status));
    const b = node('button', run.status === 'planned' ? 'Open plan' : 'Inspect', 'secondary');
    b.disabled = executing; b.addEventListener('click', () => openRun(run.id)); row.append(b); $('history').append(row);
  }
}
async function status() {
  const s = await api('/status');
  $('knowledge-status').textContent = Object.values(s.collections).reduce((a, b) => a + b, 0) + ' knowledge versions';
  $('scope-status').textContent = s.scope.customer + ' / ' + s.scope.tenant;
  $('capabilities').replaceChildren();
  for (const [key, value] of Object.entries({Store: s.backend, Embedding: s.embedding, Reranker: s.reranker, Training: 'Not required', Execution: 'Local sandbox; live SAP disabled'})) $('capabilities').append(node('dt', key), node('dd', value));
}
$('plan-button').addEventListener('click', async () => {
  const button = $('plan-button'); button.disabled = true; invalidatePlan();
  const ticket = revision, requirement = $('requirement').value;
  message('Retrieving knowledge and compiling the plan…');
  try {
    const plan = await api('/plans', {requirement});
    if (ticket !== revision) { message('Requirement changed. Generate a new plan.'); return; }
    showPlan(plan); message(plan.blockers.length ? 'This plan needs additional configuration.' : 'Plan ready. Execution uses a fresh sandbox.');
    await refresh();
  } catch (e) { if (ticket === revision) message(e.message, true); }
  finally { button.disabled = executing; }
});
$('execute').addEventListener('click', async () => {
  if (!currentPlan || executing) return;
  const id = currentPlan.id; executing = true; invalidatePlan();
  for (const key of ['plan-button', 'requirement', 'load-example']) $(key).disabled = true;
  message('Executing and verifying each step…');
  try {
    const run = await api('/plans/' + encodeURIComponent(id) + '/run', {});
    showRun(run); message(run.success ? 'Sandbox verified' + (run.knowledge_ingested ? ' · trajectory added to knowledge.' : '.') : run.error, !run.success);
    await status();
  } catch (e) { message(e.message + ' Inspect run history before creating another plan.', true); }
  finally {
    executing = false; for (const key of ['plan-button', 'requirement', 'load-example']) $(key).disabled = false;
    refresh().catch(e => message(e.message, true));
  }
});
$('load-example').addEventListener('click', () => { $('requirement').value = 'Create HTTPS → Content Modifier → Router → OData V4 with error handling.'; invalidatePlan(); });
$('requirement').addEventListener('input', invalidatePlan);
let searchRevision = 0;
$('search-form').addEventListener('submit', async event => {
  event.preventDefault(); const ticket = ++searchRevision;
  try {
    const payload = {query: $('query').value};
    if ($('search-collection').value) payload.collections = [$('search-collection').value];
    const result = await api('/search', payload); if (ticket === searchRevision) showSources(result.hits);
  } catch (e) { if (ticket === searchRevision) message(e.message, true); }
});
$('knowledge-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = $('import-knowledge'); button.disabled = true;
  $('import-message').textContent = 'Sanitizing and indexing knowledge…';
  try {
    const result = await api('/knowledge', {title: $('knowledge-title').value, source: $('knowledge-source').value, source_version: $('knowledge-version').value, collection: $('knowledge-collection').value, content: $('knowledge-content').value, approved: $('knowledge-approved').checked});
    $('import-message').textContent = result.changed ? 'Knowledge indexed in this workspace. Reuse the same title and source to update it.' : 'This version is already indexed.';
    await status();
  } catch (e) { $('import-message').textContent = e.message; }
  finally { button.disabled = false; }
});
$('refresh').addEventListener('click', () => refresh().catch(e => message(e.message, true)));
status().catch(e => { $('knowledge-status').textContent = 'Setup required'; message(e.message, true); });
refresh().catch(e => message(e.message, true));
function showConnection(s) {
  $('sap-badge').textContent = s.configured ? 'CONFIGURED · UNVALIDATED' : 'SETUP REQUIRED'; $('sap-probe').disabled = !s.configured;
  $('sap-setup').textContent = s.configured ? 'Configured host: ' + s.tenant_host + '. Check read access to continue.' : 'Configure ' + [...s.missing, ...s.invalid].join(', ') + ' in the project’s ignored .env file, then restart the app. Keep secret values out of chat.';
  const probe = s.last_probe || s;
  if (probe.checks) {
    $('sap-checks').replaceChildren();
    for (const check of probe.checks) $('sap-checks').append(node('div', check.resource + ' · ' + (check.success ? 'read access confirmed' : check.reason) + (check.status_code ? ' · HTTP ' + check.status_code : ''), 'connection-check'));
    if (probe.success) $('sap-badge').textContent = 'READ ACCESS CONFIRMED';
    else if (probe.checks.length) $('sap-badge').textContent = 'CHECK NEEDS ATTENTION';
  }
}
$('sap-probe').addEventListener('click', async () => {
  $('sap-probe').disabled = true; $('sap-setup').textContent = 'Checking read access…';
  try { showConnection(await sapApi('/probe', {})); }
  catch (e) { $('sap-setup').textContent = e.message; $('sap-probe').disabled = false; }
});
sapApi('/status').then(showConnection).catch(e => { $('sap-setup').textContent = e.message; });
