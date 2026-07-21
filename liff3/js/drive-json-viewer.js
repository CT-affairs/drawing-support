(() => {
  const $ = (id) => document.getElementById(id);
  const apiBase = () => (window.DRAWING_SUPPORT_API_BASE || '').replace(/\/$/, '');
  const fileList = $('file-list');
  const listStatus = $('list-status-message');
  const refreshButton = $('refresh-button');
  const jsonPanelTitle = $('json-panel-title');
  const jsonTree = $('json-tree');
  const jsonOutput = $('json-output');
  const expandAllButton = $('expand-all-button');
  const collapseAllButton = $('collapse-all-button');
  const toggleRawButton = $('toggle-raw-button');
  const overview = $('analysis-overview');
  const overviewContent = $('analysis-overview-content');
  const unitControls = $('unit-controls');
  const unitEditButton = $('unit-edit-button');
  const unitDialog = $('unit-dialog');
  const unitForm = $('unit-form');
  const unitSelect = $('unit-select');
  const unitCancelButton = $('unit-cancel-button');
  const unitSaveButton = $('unit-save-button');
  const unitStatus = $('unit-status-message');
  const unitNames = { 0: 'unitless', 1: 'in', 2: 'ft', 4: 'mm', 5: 'cm', 6: 'm' };
  let currentFileId = null;
  let currentData = null;

  JsonTree.attachToolbar({ tree: jsonTree, output: jsonOutput, expandAllButton, collapseAllButton, toggleRawButton });

  const text = (value) => String(value ?? '');
  const numberText = (value) => Number.isFinite(Number(value)) ? Number(value).toLocaleString('ja-JP') : '-';
  const formatSize = (value) => { const n = Number(value); return Number.isFinite(n) ? (n < 1024 ? `${n}B` : `${Math.ceil(n / 1024)}KB`) : ''; };
  const formatTime = (value) => { if (!value) return ''; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ja-JP'); };

  function unitDisplay(data) {
    const unit = data?.unit || unitNames[data?.units] || 'mm';
    const hasUnit = data?.unit !== undefined || data?.units !== undefined;
    const source = data?.units_source || (hasUnit ? 'legacy_unknown' : 'default');
    const sourceLabel = source === 'default' ? '\uFF08JSON\u8A18\u8F09\u306A\u3057\u30FB\u30C7\u30D5\u30A9\u30EB\u30C8\uFF09'
      : source === 'user_override' ? '\uFF08\u30E6\u30FC\u30B6\u30FC\u4E0A\u66F8\u304D\uFF09'
        : source === 'dxf_header' ? '\uFF08DXF\u8A18\u8F09\u5024\uFF09' : '\uFF08\u65E2\u5B58JSON\uFF09';
    return { unit, source, label: `${unit}${sourceLabel}` };
  }

  function appendGroup(parent, title, rows) {
    const group = document.createElement('section');
    group.className = 'analysis-overview-group';
    const heading = document.createElement('h3');
    heading.textContent = title;
    group.appendChild(heading);
    const list = document.createElement('dl');
    list.className = 'analysis-overview-list';
    rows.forEach(([label, value, tone]) => {
      const term = document.createElement('dt');
      const detail = document.createElement('dd');
      term.textContent = label;
      detail.textContent = value;
      if (tone) detail.className = `analysis-status-${tone}`;
      list.append(term, detail);
    });
    group.appendChild(list);
    parent.appendChild(group);
  }

  function renderOverview(data, fileName) {
    const inserts = Array.isArray(data?.inserts) ? data.inserts : [];
    const blocks = Array.isArray(data?.blocks) ? data.blocks : [];
    const entities = Array.isArray(data?.entities) ? data.entities : [];
    const layers = Array.isArray(data?.layers) ? data.layers : [];
    const roles = { target: 0, meta: 0, unknown: 0 };
    inserts.forEach((item) => { if (Object.hasOwn(roles, item?.classification?.role)) roles[item.classification.role] += 1; });
    const diagnostics = data?.diagnostics || {};
    const diagnosticRoles = diagnostics.object_classification?.role_counts;
    if (!inserts.some((item) => item?.classification?.role) && diagnosticRoles) Object.assign(roles, diagnosticRoles);
    const unit = unitDisplay(data);
    overviewContent.replaceChildren();
    const name = document.createElement('p');
    name.className = 'analysis-overview-file';
    name.textContent = fileName || 'JSON';
    overviewContent.appendChild(name);
    appendGroup(overviewContent, '\u5206\u985E\u72B6\u6CC1', [
      ['\u30E1\u30BFObject', `${numberText(roles.meta)}\u4EF6`, 'meta'],
      ['\u5BFE\u8C61Object', `${numberText(roles.target)}\u4EF6`, 'target'],
      ['\u5224\u5B9A\u4E0D\u80FD', `${numberText(roles.unknown)}\u4EF6`, roles.unknown ? 'unknown' : 'ok'],
      ['INSERT\u5408\u8A08', `${numberText(inserts.length)}\u4EF6`],
      ['\u5206\u985E\u5358\u4F4D', 'INSERT\u914D\u7F6E\u5358\u4F4D'],
    ]);
    appendGroup(overviewContent, '\u69CB\u9020\u306E\u628A\u63E1', [
      ['DXF\u30D0\u30FC\u30B8\u30E7\u30F3', text(data?.dxf_version || '\u4E0D\u660E')],
      ['\u5358\u4F4D', unit.label, unit.source === 'default' ? 'unknown' : 'ok'],
      ['\u30EC\u30A4\u30E4\u30FC', `${numberText(layers.length)}\u4EF6`],
      ['Model Space\u30A8\u30F3\u30C6\u30A3\u30C6\u30A3', `${numberText(entities.length)}\u4EF6`],
      ['\u30D6\u30ED\u30C3\u30AF\u5B9A\u7FA9', `${numberText(blocks.length)}\u4EF6`],
      ['\u30D6\u30ED\u30C3\u30AF\u5185\u90E8\u30A8\u30F3\u30C6\u30A3\u30C6\u30A3', `${numberText(blocks.reduce((sum, block) => sum + (Number(block?.entity_count) || 0), 0))}\u4EF6`],
    ]);
    const bboxCount = blocks.filter((block) => block?.bbox).length;
    const worldBboxCount = inserts.filter((item) => item?.world_bbox).length;
    appendGroup(overviewContent, '\u5F62\u72B6\u30FB\u6587\u5B57\u306E\u628A\u63E1', [
      ['\u30ED\u30FC\u30AB\u30EBbbox', `${numberText(bboxCount)} / ${numberText(blocks.length)}\u30D6\u30ED\u30C3\u30AF`],
      ['\u30EF\u30FC\u30EB\u30C9bbox', worldBboxCount ? `${numberText(worldBboxCount)} / ${numberText(inserts.length)}\u4EF6` : '\u672A\u53D6\u5F97'],
      ['\u540D\u79F0\u5FA9\u5143', `${numberText(diagnostics.name_decoding?.restored_occurrence_count)} / ${numberText(diagnostics.name_decoding?.inspected_occurrence_count)}\u4EF6`],
      ['TEXT\u5FA9\u5143', `${numberText(diagnostics.text_decoding?.restored_occurrence_count)} / ${numberText(diagnostics.text_decoding?.inspected_occurrence_count)}\u4EF6`],
      ['JSON UTF-8', diagnostics.unicode_normalization?.strict_utf8 === true ? '\u53B3\u5BC6UTF-8' : '\u8981\u78BA\u8A8D'],
    ]);
    const note = document.createElement('p');
    note.className = 'analysis-overview-note';
    note.textContent = '\u5BFE\u8C61Object\u306F\u5728\u5EAB\u30FB\u52A0\u5DE5\u5019\u88DC\u3001\u30E1\u30BFObject\u306F\u56F3\u9762\u67A0\u306A\u3069\u306E\u7BA1\u7406\u60C5\u5831\u3067\u3059\u3002\u5224\u5B9A\u4E0D\u80FD\u306F\u8981\u78BA\u8A8D\u3068\u3057\u3066\u6B8B\u3057\u307E\u3059\u3002';
    overviewContent.appendChild(note);
    unitControls.hidden = !currentFileId;
    unitSelect.value = unit.unit;
    overview.hidden = false;
  }

  function renderFiles(files) {
    fileList.replaceChildren();
    if (!files.length) { const empty = document.createElement('li'); empty.className = 'muted'; empty.textContent = '\u5BFE\u8C61JSON\u304C\u3042\u308A\u307E\u305B\u3093'; fileList.appendChild(empty); return; }
    files.forEach((file) => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'drive-file-item';
      const name = document.createElement('span'); name.className = 'drive-file-name'; name.textContent = file.name;
      const meta = document.createElement('span'); meta.className = 'drive-file-meta'; meta.textContent = [formatTime(file.modified_time), formatSize(file.size)].filter(Boolean).join(' ・ ');
      button.append(name, meta); button.addEventListener('click', () => loadFile(file.id, button));
      const item = document.createElement('li'); item.appendChild(button); fileList.appendChild(item);
    });
  }

  async function refreshList() {
    refreshButton.disabled = true;
    try {
      const response = await fetch(`${apiBase()}/api/v1/drive/list`);
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || '\u4E00\u89A7\u53D6\u5F97\u5931\u6557');
      renderFiles(body.files || []); listStatus.textContent = `${(body.files || []).length}\u4EF6\u306EJSON`;
    } catch (error) { listStatus.textContent = error.message; listStatus.className = 'status-message error'; }
    finally { refreshButton.disabled = false; }
  }

  async function loadFile(fileId, button) {
    document.querySelectorAll('.drive-file-item').forEach((item) => item.classList.remove('active'));
    button?.classList.add('active'); currentFileId = null; currentData = null; unitControls.hidden = true; overview.hidden = true;
    try {
      const response = await fetch(`${apiBase()}/api/v1/drive/file/${encodeURIComponent(fileId)}`);
      const body = await response.json();
      if (!response.ok) throw new Error(body?.error?.message || '\u30D5\u30A1\u30A4\u30EB\u53D6\u5F97\u5931\u6557');
      currentFileId = fileId; currentData = body.data; jsonPanelTitle.textContent = body.file_name || 'JSON';
      JsonTree.showResult({ tree: jsonTree, output: jsonOutput, toggleRawButton, data: currentData }); renderOverview(currentData, body.file_name);
      listStatus.textContent = '';
    } catch (error) { listStatus.textContent = error.message; listStatus.className = 'status-message error'; }
  }

  unitEditButton.addEventListener('click', () => { unitSelect.value = unitDisplay(currentData).unit; unitStatus.textContent = ''; unitStatus.className = 'status-message'; unitDialog.showModal(); });
  unitCancelButton.addEventListener('click', () => unitDialog.close());
  unitForm.addEventListener('submit', async (event) => {
    event.preventDefault(); unitSaveButton.disabled = true; unitCancelButton.disabled = true;
    try {
      const response = await fetch(`${apiBase()}/api/v1/drive/file/${encodeURIComponent(currentFileId)}/unit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ unit: unitSelect.value }) });
      const body = await response.json(); if (!response.ok) throw new Error(body?.error?.message || '\u5358\u4F4D\u66F4\u65B0\u5931\u6557');
      currentData.unit = body.unit; currentData.units_source = 'user_override'; currentData.units = { unitless: 0, in: 1, ft: 2, mm: 4, cm: 5, m: 6 }[body.unit]; renderOverview(currentData, jsonPanelTitle.textContent); unitDialog.close(); listStatus.textContent = '\u5358\u4F4D\u3092JSON\u3078\u4E0A\u66F8\u304D\u3057\u307E\u3057\u305F';
    } catch (error) { unitStatus.textContent = error.message; unitStatus.className = 'status-message error'; }
    finally { unitSaveButton.disabled = false; unitCancelButton.disabled = false; }
  });
  refreshButton.addEventListener('click', refreshList);
  refreshList();
})();
