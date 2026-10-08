const state={package:null,flow:null,deployed:false,message:null};
const el=id=>document.getElementById(id);
el('family').textContent='Integration package · '+(new URLSearchParams(location.search).get('family')||'Demo').slice(0,60);
window.sapworldState=state;
function update(message){el('status').textContent=message;el('create-package').disabled=!!state.package;el('create-flow').disabled=!state.package||!!state.flow;el('deploy').disabled=!state.flow||state.deployed;el('test-flow').disabled=!state.deployed;el('state').textContent=JSON.stringify(state,null,2);}
el('create-package').onclick=()=>{const name=el('package-name').value.trim();if(!name)return update('A package name is required.');state.package=name;update('Package created. Add an integration flow.');};
el('create-flow').onclick=()=>{const name=el('flow-name').value.trim();if(!state.package||!name)return;state.flow=name;update('Flow created. Ready to deploy.');};
el('deploy').onclick=()=>{if(!state.flow)return;state.deployed=true;update('Flow deployed. No message has been processed yet.');};
el('test-flow').onclick=()=>{if(!state.deployed)return;state.message={status:'COMPLETED',flow:state.flow};update('Test message completed successfully.');};
el('reset').onclick=()=>{Object.assign(state,{package:null,flow:null,deployed:false,message:null});update('Create a package to begin.');};
update('Create a package to begin.');
