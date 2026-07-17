// 折りたたみ式JSONツリービューア。dxf-json.htmlとdrive-json-viewer.htmlで共用する。
window.JsonTree = (() => {
  function jsonTypeSummary(value) {
    if (Array.isArray(value)) return `配列 [${value.length}]`;
    return `オブジェクト {${Object.keys(value).length}}`;
  }

  function formatPrimitive(value) {
    if (value === null) return { text: 'null', cls: 'json-value-null' };
    if (typeof value === 'string') return { text: JSON.stringify(value), cls: 'json-value-string' };
    if (typeof value === 'number') return { text: String(value), cls: 'json-value-number' };
    if (typeof value === 'boolean') return { text: String(value), cls: 'json-value-boolean' };
    return { text: String(value), cls: 'json-value-string' };
  }

  function renderEntry(key, value) {
    const node = document.createElement('div');
    node.className = 'json-node';
    const row = document.createElement('div');
    row.className = 'json-row';
    const isContainer = value !== null && typeof value === 'object';

    const toggle = document.createElement('span');
    toggle.className = 'json-toggle' + (isContainer ? '' : ' json-toggle-spacer');
    toggle.textContent = isContainer ? '▶' : '';
    row.appendChild(toggle);

    if (key !== null) {
      const keyEl = document.createElement('span');
      keyEl.className = 'json-key';
      keyEl.textContent = key;
      row.appendChild(keyEl);
      const colon = document.createElement('span');
      colon.className = 'json-colon';
      colon.textContent = ':';
      row.appendChild(colon);
    }

    if (!isContainer) {
      const formatted = formatPrimitive(value);
      const valueEl = document.createElement('span');
      valueEl.className = `json-value ${formatted.cls}`;
      valueEl.textContent = formatted.text;
      row.appendChild(valueEl);
      node.appendChild(row);
      return node;
    }

    const summary = document.createElement('span');
    summary.className = 'json-summary';
    summary.textContent = jsonTypeSummary(value);
    row.appendChild(summary);

    const childrenContainer = document.createElement('div');
    childrenContainer.className = 'json-children';
    childrenContainer.hidden = true;

    let built = false;
    function setExpanded(expand) {
      if (expand && !built) {
        built = true;
        const entries = Array.isArray(value)
          ? value.map((item, index) => [`[${index}]`, item])
          : Object.entries(value);
        if (entries.length === 0) {
          const empty = document.createElement('div');
          empty.className = 'json-empty';
          empty.textContent = Array.isArray(value) ? '(空の配列)' : '(空のオブジェクト)';
          childrenContainer.appendChild(empty);
        } else {
          entries.forEach(([childKey, childValue]) => {
            childrenContainer.appendChild(renderEntry(childKey, childValue));
          });
        }
      }
      childrenContainer.hidden = !expand;
      toggle.textContent = expand ? '▼' : '▶';
      row.setAttribute('aria-expanded', String(expand));
    }

    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    row.setAttribute('aria-expanded', 'false');
    row.addEventListener('click', () => setExpanded(childrenContainer.hidden));
    row.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        setExpanded(childrenContainer.hidden);
      }
    });

    node._setExpanded = setExpanded;
    node._childrenContainer = childrenContainer;
    node.appendChild(row);
    node.appendChild(childrenContainer);
    return node;
  }

  function build(container, data) {
    container.innerHTML = '';
    const entries = Array.isArray(data) ? data.map((item, index) => [`[${index}]`, item]) : Object.entries(data || {});
    entries.forEach(([key, value]) => container.appendChild(renderEntry(key, value)));
  }

  function walkNodes(container, visit) {
    Array.from(container.children).forEach((node) => {
      if (!node.classList || !node.classList.contains('json-node')) return;
      visit(node);
      if (node._childrenContainer) walkNodes(node._childrenContainer, visit);
    });
  }

  function expandAll(container) {
    walkNodes(container, (node) => { if (node._setExpanded) node._setExpanded(true); });
  }

  function collapseAll(container) {
    walkNodes(container, (node) => { if (node._setExpanded) node._setExpanded(false); });
  }

  function attachToolbar({ tree, output, expandAllButton, collapseAllButton, toggleRawButton }) {
    if (expandAllButton) expandAllButton.addEventListener('click', () => expandAll(tree));
    if (collapseAllButton) collapseAllButton.addEventListener('click', () => collapseAll(tree));
    if (toggleRawButton) {
      toggleRawButton.addEventListener('click', () => {
        const showRaw = output.hidden;
        output.hidden = !showRaw;
        tree.hidden = showRaw;
        toggleRawButton.textContent = showRaw ? 'ツリー表示に戻す' : 'RAW JSONを表示';
        toggleRawButton.setAttribute('aria-pressed', String(showRaw));
      });
    }
  }

  function showResult({ tree, output, toggleRawButton, data }) {
    output.textContent = JSON.stringify(data, null, 2);
    build(tree, data);
    output.hidden = true;
    tree.hidden = false;
    if (toggleRawButton) {
      toggleRawButton.textContent = 'RAW JSONを表示';
      toggleRawButton.setAttribute('aria-pressed', 'false');
    }
  }

  return { build, expandAll, collapseAll, attachToolbar, showResult };
})();
