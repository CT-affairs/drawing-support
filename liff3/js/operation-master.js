(() => {
  const apiBase = () => (window.DRAWING_SUPPORT_API_BASE || '').replace(/\/$/, '');
  const $ = (id) => document.getElementById(id);
  const fields = {
    id: $('operation-id'), name: $('operation-name'), instruction: $('operation-instruction'),
    actions: $('operation-actions'), description: $('operation-description'), active: $('operation-active'),
  };
  const list = $('operation-list');
  const status = $('operation-status');
  const setStatus = (message, error = false) => { status.textContent = message; status.className = `status-message${error ? ' error' : ''}`; };
  const clearForm = () => { fields.id.value = ''; fields.name.value = ''; fields.instruction.value = ''; fields.actions.value = ''; fields.description.value = ''; fields.active.checked = true; fields.id.focus(); };
  const fillForm = (item) => { fields.id.value = item.operation_id || ''; fields.name.value = item.name || ''; fields.instruction.value = item.instruction || ''; fields.actions.value = (item.actions || []).join(','); fields.description.value = item.description || ''; fields.active.checked = item.active !== false; window.scrollTo({ top: 0, behavior: 'smooth' }); };

  function render(items) {
    list.replaceChildren();
    if (!items.length) { list.textContent = 'No operations registered.'; return; }
    items.forEach((item) => {
      const card = document.createElement('article'); card.className = 'operation-item';
      const heading = document.createElement('h3');
      heading.append(`${item.operation_id} / ${item.name}`);
      const instruction = document.createElement('p'); instruction.textContent = item.instruction || '';
      const meta = document.createElement('p'); meta.className = 'operation-meta'; meta.textContent = `actions: ${(item.actions || []).join(', ') || '-'} / ${item.active === false ? 'inactive' : 'active'} / version: ${item.version || 1}`;
      const actions = document.createElement('span'); actions.className = 'operation-item-actions';
      const edit = document.createElement('button'); edit.className = 'btn-secondary'; edit.type = 'button'; edit.textContent = 'Edit'; edit.addEventListener('click', () => fillForm(item));
      const remove = document.createElement('button'); remove.className = 'btn-secondary'; remove.type = 'button'; remove.textContent = 'Delete'; remove.addEventListener('click', () => removeOperation(item.operation_id));
      actions.append(edit, remove); heading.appendChild(actions); card.append(heading, instruction, meta); list.appendChild(card);
    });
  }

  async function loadOperations() {
    setStatus('Loading...');
    try { const response = await fetch(`${apiBase()}/api/v1/operations`); const body = await response.json(); if (!response.ok) throw new Error(body?.error?.message || 'Load failed'); render(body.operations || []); setStatus(`${(body.operations || []).length} operation(s) loaded`); }
    catch (error) { setStatus(error.message, true); }
  }

  async function saveOperation() {
    const id = fields.id.value.trim().toUpperCase();
    const payload = { name: fields.name.value.trim(), instruction: fields.instruction.value.trim(), actions: fields.actions.value.split(',').map((item) => item.trim()).filter(Boolean), description: fields.description.value.trim(), active: fields.active.checked };
    if (!/^OP\d{3,}$/.test(id) || !payload.name || !payload.instruction) { setStatus('Enter an OP001-style ID, name, and instruction.', true); return; }
    try { const response = await fetch(`${apiBase()}/api/v1/operations/${encodeURIComponent(id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); const body = await response.json(); if (!response.ok) throw new Error(body?.error?.message || 'Save failed'); setStatus(`${id} saved`); await loadOperations(); }
    catch (error) { setStatus(error.message, true); }
  }

  async function removeOperation(id) {
    if (!window.confirm(`Delete ${id}?`)) return;
    try { const response = await fetch(`${apiBase()}/api/v1/operations/${encodeURIComponent(id)}`, { method: 'DELETE' }); if (!response.ok) { const body = await response.json(); throw new Error(body?.error?.message || 'Delete failed'); } setStatus(`${id} deleted`); await loadOperations(); }
    catch (error) { setStatus(error.message, true); }
  }

  $('save-operation').addEventListener('click', saveOperation);
  $('clear-operation').addEventListener('click', clearForm);
  $('reload-operations').addEventListener('click', loadOperations);
  loadOperations();
})();
