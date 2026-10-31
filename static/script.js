/* Small frontend enhancements; no backend/database logic is changed. */
document.addEventListener('DOMContentLoaded', () => {
  // Mark common status/flash messages with consistent styling.
  document.querySelectorAll('body > p').forEach((p) => {
    const text = (p.textContent || '').trim().toLowerCase();
    if (text && /success|logged out|logged in|registered|invalid|must login|already marked|session ended|enter subject|invalid qr|please login|you must login/.test(text)) {
      p.classList.add('flash-message');
      if (/invalid|must login|already marked|enter subject|you must login/.test(text)) p.classList.add('error');
    }
  });

  // Add client-side search to tables, without changing server-side data.
  document.querySelectorAll('table').forEach((table, index) => {
    const rows = table.querySelectorAll('tr');
    if (rows.length < 3) return;
    const tools = document.createElement('div');
    tools.className = 'table-tools';
    const search = document.createElement('input');
    search.type = 'search';
    search.className = 'table-search';
    search.placeholder = 'Search records…';
    search.setAttribute('aria-label', 'Search table records');
    search.id = `table-search-${index}`;
    tools.appendChild(search);
    table.parentNode.insertBefore(tools, table);
    search.addEventListener('input', () => {
      const term = search.value.trim().toLowerCase();
      table.querySelectorAll('tr').forEach((row, rowIndex) => {
        if (rowIndex === 0) return;
        row.hidden = !row.textContent.toLowerCase().includes(term);
      });
    });
  });

  // Ask before ending an active teacher attendance session.
  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const submitter = event.submitter;
      const label = (submitter?.textContent || submitter?.value || '').trim().toLowerCase();
      if (label.includes('end session')) {
        const ok = window.confirm('End this attendance session? Students will no longer be able to mark attendance for it.');
        if (!ok) event.preventDefault();
      }
    });
  });
});
