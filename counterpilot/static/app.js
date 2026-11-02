/**
 * CounterPilot Frontend Client Application
 *
 * Architectural Role:
 *   Manages single-page user interactions, query dispatch, async race-condition protection,
 *   state synchronization between natural language text and manual criteria controls,
 *   and explicit safety verification gates (vehicle acknowledgment and VIN confirmation).
 *
 * Core Design Principles:
 *   1. Async Request Versioning:
 *      Uses monotonically increasing integers (`searchVersion`, `vinVersion`) to discard
 *      out-of-order or stale HTTP responses when rapid typing or prompt switching occurs.
 *   2. Stale Result Clearing:
 *      Whenever the customer edits text, changes vehicle selection, or modifies criteria,
 *      previous candidate cards and answers are cleared immediately, forcing fresh validation.
 *   3. Vehicle Configuration Acknowledgment Barrier:
 *      Candidate part cards are NEVER rendered immediately upon finding matches.
 *      The user must first explicitly review and click an acknowledgment button confirming that
 *      the vehicle's engine, trim, and drivetrain match the customer's vehicle.
 *   4. Identity vs Fitment Separation:
 *      Decoded VIN fields are shown for confirmation before they are copied to criteria fields.
 */

const $ = id => document.getElementById(id);
const fields = ['year','make','model','category','position','brake_package'];
let catalog = [], searchVersion = 0, vinVersion = 0;

/** Utility helper for safe DOM element construction without innerHTML injection risks. */
function node(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

/** Synchronize manual form inputs with a Criteria object. */
function fill(criteria) {
  for (const f of fields) $(f).value = criteria[f] ?? '';
}

/** Reset all form fields, candidate results, and VIN inspection panels to initial state. */
function reset() {
  vinVersion++;
  $('vin').value = '';
  $('vin-result').replaceChildren();
  document.querySelector('details.vin').open = false;
  $('details').open = false;
  searchVersion++;
  fill({});
  $('vehicle').value = '';
  $('request').value = '';
  $('result-body').replaceChildren(node('p', 'Ready for a new request.', 'hint'));
}

/** Collect non-empty manual override fields from the UI form. */
function readCriteria() {
  const c = {};
  for (const f of fields) {
    if ($(f).value) c[f] = f === 'year' ? Number($(f).value) : $(f).value.trim();
  }
  return c;
}

/** Centralized POST wrapper with unified JSON error extraction. */
async function api(url, data) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  const payload = await r.json();
  if (!r.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Check the entered values and try again.');
  return payload;
}

/**
 * Render candidate part cards once the user has verified the vehicle configuration.
 * Displays application evidence, restrictions, and separate unverified interchange cross-references.
 */
function showCards(result, parent) {
  for (const p of result.candidates) {
    const card = node('article', undefined, 'candidate');
    card.append(node('span', 'FICTIONAL APPLICATION', 'badge'), node('h3', p.name), node('p', p.part_number, 'part-number'));
    card.append(node('p', result.vehicle.description));
    for (const evidence of p.evidence) {
      card.append(node('p', evidence.statement), node('p', 'Source: ' + evidence.source, 'hint'));
    }
    const ul = node('ul');
    for (const restriction of p.restrictions) ul.append(node('li', restriction));
    card.append(ul);
    // Cross-references are intentionally relegated to collapsible details to emphasize
    // that they are reference notes, NOT primary fitment evidence.
    const refs = node('details');
    refs.append(node('summary', 'Cross-reference notes'));
    for (const ref of p.interchanges) refs.append(node('p', ref.number + ' — ' + ref.status));
    card.append(refs);
    parent.append(card);
  }
}

/**
 * Render API response into the results panel.
 * Handles three primary statuses:
 *   - 'candidates': Shows vehicle acknowledgment prompt before revealing candidate cards.
 *   - 'needs_clarification': Displays interactive question buttons or inputs for missing fields.
 *   - 'outside_coverage': Explains that the vehicle or part is outside demo fixtures.
 */
function render(result) {
  const body = $('result-body');
  body.replaceChildren();
  const badge = node(
    'span',
    result.status === 'candidates' ? 'APPLICATION RECORD FOUND' :
    result.status === 'needs_clarification' ? 'ONE MORE DETAIL' : 'OUTSIDE DEMO COVERAGE',
    'badge ' + (result.status === 'needs_clarification' ? 'question' : '')
  );
  body.append(badge, node('p', result.message, 'message'));
  const values = Object.entries(result.criteria).filter(([, v]) => v !== null).map(([k, v]) => k.replaceAll('_', ' ') + ': ' + v);
  body.append(node('div', values.length ? values.join(' · ') : 'No criteria yet.', 'criteria'));
  body.append(node('p', 'Interpretation: ' + result.provider + ' · Matching: deterministic fictional catalog', 'hint'));

  // Render clarification questions and options (e.g. front vs rear, standard vs heavy-duty).
  for (const q of result.questions) {
    const block = node('div', undefined, 'question-block');
    block.append(node('p', q.label));
    if (q.options.length) {
      const choices = node('div', undefined, 'choices');
      for (const option of q.options) {
        const b = node('button', option);
        b.type = 'button';
        b.onclick = () => {
          $(q.field).value = option;
          runSearch();
        };
        choices.append(b);
      }
      block.append(choices);
    } else {
      const b = node('button', 'Enter ' + q.field);
      b.type = 'button';
      b.onclick = () => {
        $('details').open = true;
        $(q.field).focus();
      };
      block.append(b);
    }
    body.append(block);
    $('details').open = true;
  }

  // Safety Gate: Candidate parts are held behind explicit vehicle confirmation.
  if (result.candidates.length) {
    const confirm = node('div', undefined, 'confirm');
    confirm.append(
      node('strong', 'Confirm the vehicle configuration'),
      node('p', result.vehicle.year + ' ' + result.vehicle.make + ' ' + result.vehicle.model + ' · ' + result.vehicle.description)
    );
    confirm.append(node('p', 'The demo covers this exact configuration. If these details differ, the application is outside the demonstrated coverage.'));
    const b = node('button', 'These vehicle details match · inspect candidates');
    b.type = 'button';
    b.onclick = () => {
      confirm.replaceChildren(node('p', 'Vehicle details acknowledged for this demonstration.'));
      showCards(result, body);
    };
    confirm.append(b);
    body.append(confirm);
  }
}

/** Execute search query with race-condition protection and busy state management. */
async function runSearch() {
  const version = ++searchVersion;
  const b = $('submit');
  b.disabled = true;
  $('results').setAttribute('aria-busy', 'true');
  try {
    const data = await api('/api/search', {
      text: $('request').value,
      provider: $('provider').value,
      criteria: readCriteria()
    });
    // Discard response if a newer search was dispatched while waiting.
    if (version !== searchVersion) return;
    fill(data.criteria);
    render(data);
  } catch (e) {
    if (version === searchVersion) {
      $('result-body').replaceChildren(
        node('span', 'LOOKUP UNAVAILABLE', 'badge error'),
        node('p', e.message, 'error-text'),
        node('p', 'Switch to offline or manual interpretation and retry.', 'hint')
      );
    }
  } finally {
    b.disabled = false;
    $('results').setAttribute('aria-busy', 'false');
  }
}

// Event Bindings & Stale State Clearing

$('search-form').onsubmit = e => {
  e.preventDefault();
  runSearch();
};

$('reset').onclick = reset;

// Typing in the text area invalidates previously matched manual criteria and cards.
$('request').addEventListener('input', () => {
  searchVersion++;
  fill({});
  $('vehicle').value = '';
  $('result-body').replaceChildren(node('p', 'Request changed. Run a new application check.', 'hint'));
});

// Example prompt buttons clear state, load example text, and run search.
document.querySelectorAll('[data-prompt]').forEach(b => {
  b.onclick = () => {
    reset();
    $('request').value = b.dataset.prompt;
    runSearch();
  };
});

// Selecting a known demo vehicle populates Year/Make/Model and clears prior brake package.
$('vehicle').onchange = () => {
  searchVersion++;
  $('brake_package').value = '';
  $('result-body').replaceChildren(node('p', 'Vehicle changed. Run a new application check.', 'hint'));
  const v = catalog.find(v => v.id === $('vehicle').value);
  for (const f of ['year', 'make', 'model']) $(f).value = v ? v[f] : '';
};

// Modifying manual fields clears old results to prevent displaying mismatched evidence.
for (const f of fields) {
  $(f).addEventListener('input', () => {
    searchVersion++;
    $('result-body').replaceChildren(node('p', 'Details changed. Run the application check again.', 'hint'));
  });
}

// Switching provider: if manual is selected, open the details drawer automatically.
$('provider').onchange = () => {
  searchVersion++;
  fill({});
  $('vehicle').value = '';
  if ($('provider').value === 'manual') $('details').open = true;
  $('result-body').replaceChildren(node('p', 'Interpretation changed. Run a new application check.', 'hint'));
};

// VIN Input & Confirmation Flow
$('vin').oninput = () => {
  vinVersion++;
  $('vin-result').replaceChildren();
};

$('vin-form').onsubmit = async e => {
  e.preventDefault();
  const version = ++vinVersion;
  $('vin-submit').disabled = true;
  $('vin-result').replaceChildren(node('p', 'Decoding identity…', 'hint'));
  try {
    const data = await api('/api/vin', { vin: $('vin').value });
    if (version !== vinVersion) return;
    const v = data.vehicle;
    const display = node('div', undefined, 'confirm');
    display.append(node('p', [v.model_year, v.make, v.model, v.trim, v.engine?.displacement_l && v.engine.displacement_l + 'L', v.drivetrain].filter(Boolean).join(' · ')));
    display.append(node('p', data.message));
    if (v.api_error_code && v.api_error_code !== '0') {
      display.append(node('p', 'Decoder reported a warning. Review all fields before use.', 'error-text'));
    }
    // Explicit confirmation button: user must click this before decoded identity is populated into criteria.
    const b = node('button', 'Confirm identity & use these fields');
    b.type = 'button';
    b.onclick = () => {
      searchVersion++;
      for (const f of ['year', 'make', 'model']) $(f).value = f === 'year' ? (v.model_year || '') : (v[f] || '');
      $('vehicle').value = '';
      $('details').open = true;
      $('result-body').replaceChildren(node('p', 'VIN identity copied. Review configuration details and run the application check.', 'hint'));
      display.replaceChildren(node('p', 'Identity copied. Brake package and exact configuration still need confirmation.'));
    };
    display.append(b);
    $('vin-result').replaceChildren(display);
  } catch (e) {
    if (version === vinVersion) {
      $('vin-result').replaceChildren(node('p', e.message, 'error-text'));
    }
  } finally {
    $('vin-submit').disabled = false;
  }
};

// Bootstrap catalog coverage and provider configuration on page load.
fetch('/api/catalog')
  .then(r => {
    if (!r.ok) throw Error();
    return r.json();
  })
  .then(data => {
    catalog = data.vehicles;
    for (const v of catalog) {
      const o = node('option', v.year + ' ' + v.make + ' ' + v.model + ' · ' + v.description);
      o.value = v.id;
      $('vehicle').append(o);
    }
    $('provider').value = data.default_provider;
    $('provider-note').textContent = data.meta_configured
      ? 'Meta key is configured; live integration remains unverified until a successful request.'
      : 'Offline mode is ready. Meta requires a local MODEL_API_KEY; no live call has been verified.';
  })
  .catch(() => {
    $('provider-note').textContent = 'Could not load coverage. Refresh the page after starting the local server.';
  });
