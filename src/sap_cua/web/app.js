const $ = id => document.getElementById(id);
async function api(path, options={}) {
  const response = await fetch(path, { ...options, headers: {'Content-Type':'application/json','X-SAP-CUA':'workbench', ...options.headers} });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}
function text(tag, value, className) { const el=document.createElement(tag); el.textContent=value; if(className) el.className=className; return el; }
function show(run) {
  $('trace').replaceChildren(); $('result-badge').textContent=run.status.toUpperCase();
  run.steps.forEach((step,index) => { const row=text('div','','step'); row.append(text('b',String(index+1).padStart(2,'0'))); const body=document.createElement('div'); body.append(text('strong',step.action.intent.replaceAll('_',' ')), text('small',step.result.success ? 'Executed in isolated sandbox' : step.result.error)); row.append(body); $('trace').append(row); });
  const verification=text('p',run.success ? '✓ Independent verification passed' : (run.error || 'Verification failed'), run.success?'succeeded':'failed'); $('trace').append(verification);
  $('evidence').textContent=JSON.stringify(run,null,2);
}
async function history() { const runs=await api('/api/runs'); $('history').replaceChildren(); if(!runs.length) $('history').textContent='No runs yet. Run the example to begin.'; runs.forEach(run=>{const row=text('div','','history-row'); const info=text('div',run.instruction); info.append(text('small',` · ${new Date(run.created*1000).toLocaleString()} · ${run.status}`)); const button=text('button','View','secondary'); button.onclick=()=>show(run); row.append(info,button); $('history').append(row);}); }
async function example() { $('plan').value=JSON.stringify(await api('/api/example'),null,2); }
function error(err) { $('message').textContent=err.message; $('message').className='failed'; }
$('load-example').onclick=()=>example().catch(error);
$('refresh').onclick=()=>history().catch(error);
$('execute').onclick=async()=>{const button=$('execute');button.disabled=true;$('message').textContent='Running and verifying…';try { const run=await api('/api/runs',{method:'POST',body:JSON.stringify(JSON.parse($('plan').value))});show(run);await history();$('message').textContent=run.success?'Run complete. Evidence saved.':run.error;$('message').className=run.success?'succeeded':'failed';}catch(err){error(err);}finally{button.disabled=false;}};
(async()=>{await example();await history();const c=await api('/api/capabilities');$('model-status').textContent=c.model.downloaded?'Downloaded · unvalidated':'Download pending';for(const [name,value] of Object.entries({'SAP connection':c.sap_live,'Model training':c.training,'RL training':c.rl,'Executors':Object.entries(c.executors).map(([k,v])=>`${k}: ${v}`).join(' · ')})) $('capabilities').append(text('dt',name),text('dd',value.replaceAll('_',' ')));})().catch(error);
