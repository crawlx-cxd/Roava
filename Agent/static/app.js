const form = document.querySelector('#plan-form');
const submitButton = document.querySelector('#submit');
const statusNode = document.querySelector('#status');
const outputSection = document.querySelector('#output-section');
const planContent = document.querySelector('#plan-content');
const planSummary = document.querySelector('#plan-summary');
const reviewEditor = document.querySelector('#review-editor');
const reviewConfirm = document.querySelector('#review-confirm');
const finalCheckButton = document.querySelector('#final-check');
const reviewStatus = document.querySelector('#review-status');
const toast = document.querySelector('#toast');

let latestPlan = '';
let latestRequest = '';
let toastTimer;

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

function renderMarkdown(markdown) {
  const lines = markdown.split(/\r?\n/);
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index += 1; continue; }

    if (line.includes('|') && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[index + 1])) {
      const rows = [line];
      index += 2;
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) rows.push(lines[index++].trim());
      const cells = rows.map((row) => row.replace(/^\|?|\|?$/g, '').split('|').map((cell) => cell.trim()));
      const headers = cells[0] || [];
      const bodyRows = cells.slice(1);
      blocks.push(`<div class="table-scroll"><table><thead><tr>${headers.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join('')}</tr></thead><tbody>${bodyRows.map((row) => `<tr>${headers.map((_, cellIndex) => `<td>${inlineMarkdown(row[cellIndex] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      blocks.push(`<h3>${inlineMarkdown(heading[2])}</h3>`);
      index += 1;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) items.push(`<li>${inlineMarkdown(lines[index++].replace(/^\s*[-*]\s+/, ''))}</li>`);
      blocks.push(`<ul>${items.join('')}</ul>`);
      continue;
    }
    if (/^\d+[.)]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*\d+[.)]\s+/.test(lines[index])) items.push(`<li>${inlineMarkdown(lines[index++].replace(/^\s*\d+[.)]\s+/, ''))}</li>`);
      blocks.push(`<ol>${items.join('')}</ol>`);
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^(#{1,3}\s|[-*]\s|\d+[.)]\s)/.test(lines[index].trim())) paragraph.push(lines[index++].trim());
    blocks.push(`<p>${paragraph.map(inlineMarkdown).join('<br>')}</p>`);
  }
  return blocks.join('');
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove('show'), 2200);
}

function setStatus(message, kind = '') {
  statusNode.className = `status-message ${kind}`.trim();
  statusNode.textContent = message;
}

function setReviewStatus(message, kind = '') {
  reviewStatus.className = `review-status ${kind}`.trim();
  reviewStatus.textContent = message;
}

async function checkServer() {
  try {
    const response = await fetch('/api/health');
    const state = await response.json();
    if (!state.ready) {
      const message = state.message || (state.ollama_running
        ? `Ollama is running, but ${state.model} is not installed. Run: ollama pull ${state.model}`
        : 'No AI provider connected. Add GEMINI_API_KEY in .env or start Ollama.');
      setStatus(message, 'error');
    }
  } catch {
    setStatus('The local planner is not reachable. Check that its PowerShell window is still running.', 'error');
  }
}

function buildRequest() {
  const destination = document.querySelector('#destination').value.trim();
  const duration = document.querySelector('#duration').value;
  const budget = document.querySelector('#budget').value;
  const pace = form.querySelector('input[name="pace"]:checked')?.value || 'relaxed';
  const interests = [...form.querySelectorAll('input[name="interest"]:checked')].map((input) => input.value);
  const notes = document.querySelector('#notes').value.trim();
  const interestText = interests.length ? interests.join(', ') : 'general sightseeing and local highlights';
  const budgetText = { budget: 'budget-friendly', moderate: 'moderate', luxury: 'luxury' }[budget];
  let request = `Plan a ${pace} ${duration}-day trip to ${destination}, focused on ${interestText}, with a ${budgetText} budget.`;
  if (notes) request += ` Additional preferences: ${notes}`;
  request += ' Create a practical day-by-day itinerary with a manageable number of stops, sensible sequencing, and time to rest. Include sources and note details that should be verified.';
  return { request, destination, duration, budget, pace };
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const trip = buildRequest();
  const buttonLabel = submitButton.querySelector('.button-label');
  const progressMessages = [
    'Getting a feel for your trip…',
    'Finding places that fit your interests…',
    'Putting your days in a comfortable order…'
  ];
  let progressIndex = 0;
  submitButton.disabled = true;
  buttonLabel.textContent = 'Planning your trip…';
  submitButton.querySelector('.button-arrow').textContent = '…';
  setStatus(`<span class="spinner"></span>${progressMessages[0]}`, 'loading');
  const progressTimer = window.setInterval(() => {
    progressIndex = (progressIndex + 1) % progressMessages.length;
    statusNode.innerHTML = `<span class="spinner"></span>${progressMessages[progressIndex]}`;
  }, 5000);

  try {
    const response = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request: trip.request })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The planner could not complete that request.');

    latestPlan = data.answer || '';
    latestRequest = trip.request;
    planSummary.textContent = `${trip.destination} · ${trip.duration} ${Number(trip.duration) === 1 ? 'day' : 'days'} · ${trip.pace} pace · ${trip.budget} budget`;
    planContent.innerHTML = renderMarkdown(latestPlan || 'The planner returned an empty itinerary.');
    reviewEditor.value = latestPlan;
    reviewConfirm.checked = false;
    finalCheckButton.disabled = true;
    setReviewStatus('Make any edits you like, then confirm below to run the final check.');
    outputSection.classList.remove('hidden');
    outputSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setStatus(`Your plan is ready · ${data.steps} agent steps`);
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    window.clearInterval(progressTimer);
    submitButton.disabled = false;
    buttonLabel.textContent = 'Build my itinerary';
    submitButton.querySelector('.button-arrow').textContent = '↗';
  }
});

reviewEditor.addEventListener('input', () => {
  latestPlan = reviewEditor.value;
  planContent.innerHTML = renderMarkdown(latestPlan || 'Your edited itinerary preview will appear here.');
  reviewConfirm.checked = false;
  finalCheckButton.disabled = true;
  setReviewStatus('Edits saved in the preview. Confirm your review to run the final check.');
});

reviewConfirm.addEventListener('change', () => {
  finalCheckButton.disabled = !reviewConfirm.checked || !reviewEditor.value.trim();
  if (reviewConfirm.checked) setReviewStatus('Ready for the final check.');
});

finalCheckButton.addEventListener('click', async () => {
  if (!reviewConfirm.checked || !reviewEditor.value.trim()) return;
  const buttonLabel = finalCheckButton.querySelector('.button-label');
  finalCheckButton.disabled = true;
  buttonLabel.textContent = 'Checking itinerary…';
  finalCheckButton.querySelector('.button-arrow').textContent = '…';
  reviewStatus.className = 'review-status';
  reviewStatus.innerHTML = '<span class="spinner"></span> Checking trip length, table structure, and consistency…';

  try {
    const response = await fetch('/api/final-check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request: latestRequest, draft: reviewEditor.value })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The final check could not be completed.');

    latestPlan = data.answer || reviewEditor.value;
    reviewEditor.value = latestPlan;
    planContent.innerHTML = renderMarkdown(latestPlan);
    reviewConfirm.checked = true;
    setReviewStatus('Final check complete. The checked itinerary is shown above and in the editor.');
    setStatus('Your itinerary has passed the final consistency check.');
  } catch (error) {
    setReviewStatus(error.message, 'error');
  } finally {
    buttonLabel.textContent = 'Check & finalize';
    finalCheckButton.querySelector('.button-arrow').textContent = '✓';
    finalCheckButton.disabled = !reviewConfirm.checked;
  }
});

document.querySelector('#copy-button').addEventListener('click', async () => {
  if (!latestPlan) return;
  try {
    await navigator.clipboard.writeText(latestPlan);
    showToast('Itinerary copied to clipboard');
  } catch {
    showToast('Clipboard access is unavailable in this browser');
  }
});

document.querySelector('#download-button').addEventListener('click', () => {
  if (!latestPlan) return;
  const destination = document.querySelector('#destination').value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'trip';
  const file = new Blob([latestPlan], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${destination}-itinerary.md`;
  link.click();
  URL.revokeObjectURL(url);
  showToast('Your itinerary download has started');
});

checkServer();
