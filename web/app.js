const byId = (id) => document.getElementById(id);
const sourceText = byId('source-text');
const noiseRate = byId('noise-rate');
const faultToggle = byId('fault-toggle');
const faultBit = byId('fault-bit');
const runButton = byId('run-simulation');
const stageTitles = [
  ['SOURCE INPUT', 'ASCII conversion'],
  ['SOURCE ENCODING', 'Huffman compression'],
  ['CHANNEL ENCODING', 'Hamming (7,4)'],
  ['NOISY CHANNEL', 'Bit-flip transmission'],
  ['CHANNEL DECODING', 'Syndrome & correction'],
  ['SOURCE DECODING', 'Message reconstruction']
];
let runNumber = 1;
let activeStage = 0;
let simulationData = null;
let toastTimer;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function showToast(message) {
  const toast = byId('toast');
  toast.textContent = message;
  toast.classList.add('is-visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 3800);
}

function displayCharacter(character) {
  if (character === 'SPACE') return '␠';
  if (character === 'LF') return '↵';
  if (character === 'TAB') return '⇥';
  if (character === 'CR') return '␍';
  return character;
}

function heading(index, description, tag) {
  const [eyebrow, title] = stageTitles[index];
  return `<div class="stage-view-heading"><div><span class="eyebrow">${eyebrow} <span>${String(index + 1).padStart(2, '0')} / 06</span></span><h3>${title}</h3><p>${description}</p></div><span class="stage-view-tag">${tag}</span></div>`;
}

function output(label, value, options = {}) {
  const { full = false, pre = false, meta = '' } = options;
  const classes = ['stage-output', full ? 'full-width' : ''].filter(Boolean).join(' ');
  return `<div class="${classes}"><div class="output-label"><span>${label}</span><span>${meta}</span></div><div class="output-value${pre ? ' pre-wrap' : ''}">${value}</div></div>`;
}

function bitWord(bits, block, mode) {
  const changed = new Set(block?.changed_positions || []);
  const correction = block?.error_position;
  return `<span class="bit-word">${[...bits].map((bit, index) => {
    const position = index + 1;
    let state = mode === 'source'
      ? ' data'
      : position === 1 || position === 2 || position === 4 ? ' parity' : ' data';
    if (mode === 'received' && changed.has(position)) state = ' corrupted';
    if (mode === 'corrected' && correction === position) state = ' corrected';
    return `<span class="bit${state}" title="Position ${position}${state.includes('parity') ? ', parity bit' : ', data bit'}">${bit}</span>`;
  }).join('')}</span>`;
}

function bitLegend() {
  return '<div class="bit-legend"><span><i class="legend-chip"></i>DATA BIT</span><span><i class="legend-chip parity"></i>PARITY BIT</span><span><i class="legend-chip corrupted"></i>FLIPPED IN CHANNEL</span><span><i class="legend-chip corrected"></i>DECODER CORRECTION</span></div>';
}

function stageBlocks(blocks, kind) {
  return `<div class="stage-block-list">${blocks.map((block) => {
    if (kind === 'encode') {
      return `<div class="stage-block"><span class="stage-block-label">BLOCK ${String(block.number).padStart(2, '0')}</span><div>${bitWord(block.source, null, 'source')} <span class="stage-block-note">→</span> ${bitWord(block.transmitted, null, 'transmitted')}</div><span class="stage-block-note">7 BITS</span></div>`;
    }
    if (kind === 'channel') {
      const errorText = block.changed_positions.length
        ? `FLIP${block.changed_positions.length > 1 ? 'S' : ''} AT ${block.changed_positions.map((position) => (block.number - 1) * 7 + position).join(', ')}`
        : 'NO FLIP';
      return `<div class="stage-block"><span class="stage-block-label">BLOCK ${String(block.number).padStart(2, '0')}</span><div>${bitWord(block.transmitted, null, 'transmitted')} <span class="stage-block-note">→</span> ${bitWord(block.received, block, 'received')}</div><span class="stage-block-note">${errorText}</span></div>`;
    }
    return `<div class="stage-block"><span class="stage-block-label">BLOCK ${String(block.number).padStart(2, '0')}</span><div>${bitWord(block.received, block, 'received')} <span class="stage-block-note">→</span> ${bitWord(block.corrected_codeword, block, 'corrected')} <span class="stage-block-note">→ ${block.data_bits}</span></div><span class="stage-block-note">S=${block.syndrome} (${block.syndrome_value})${block.error_position ? ` · BIT ${block.error_position} FLIPPED` : ' · CLEAN'}</span></div>`;
  }).join('')}</div>`;
}

function renderAsciiStage(data) {
  const bytes = data.ascii.map(({ character, binary }) => {
    const label = displayCharacter(character);
    return `<span class="ascii-byte" title="${escapeHtml(character)} = ${binary}">${escapeHtml(label)} <b>${binary}</b></span>`;
  }).join('');
  return `${heading(0, 'Each input character becomes one 8-bit ASCII byte.', `${data.source_text.length} CHAR${data.source_text.length === 1 ? '' : 'S'}`)}
    <div class="stage-columns">
      ${output('ORIGINAL TEXT', escapeHtml(data.source_text), { pre: true, meta: `${data.metrics.original_bits} BITS` })}
      ${output('ASCII BYTES', bytes + (data.ascii_truncated ? '<span class="ascii-byte">… remaining bytes shown below</span>' : ''), { meta: '8 BITS / CHARACTER' })}
      ${output('CONTINUOUS ASCII BITSTREAM', `<div class="bit-text">${data.ascii_bits}</div>`, { full: true, meta: `${data.ascii_bits.length} BITS` })}
    </div>`;
}

function renderHuffmanStage(data) {
  const rows = data.codebook.map((entry) => `<tr><td>${escapeHtml(displayCharacter(entry.character))}</td><td>${entry.frequency}</td><td><code>${entry.code}</code></td><td>${entry.length}</td></tr>`).join('');
  return `${heading(1, 'Least-frequent nodes are merged first; left edges are 0 and right edges are 1.', `${data.codebook.length} SYMBOLS`)}
    <div class="stage-columns">
      ${output('FREQUENCY TABLE & CODEBOOK', `<table class="stage-table"><thead><tr><th>SYMBOL</th><th>FREQ.</th><th>CODEWORD</th><th>BITS</th></tr></thead><tbody>${rows}</tbody></table>`, { meta: 'PREFIX-FREE CODES' })}
      ${output('SERIALIZED HUFFMAN TREE', `<pre class="tree-view">${escapeHtml(JSON.stringify(data.huffman_tree, null, 2))}</pre>`, { meta: 'TREE STRUCTURE' })}
      ${output('HUFFMAN ENCODED STREAM', `<div class="bit-text">${data.compressed_bits}</div>`, { full: true, meta: `${data.compressed_bits.length} BITS` })}
      ${output('4-BIT ALIGNMENT', `<div class="bit-text">${data.compressed_bits}<span class="padding-bits">${'0'.repeat(data.padding)}</span></div>`, { full: true, meta: `${data.padding} ZERO PADDING BIT${data.padding === 1 ? '' : 'S'}` })}
    </div>`;
}

function renderHammingStage(data) {
  return `${heading(2, 'The padded source stream is split into 4-bit words and encoded with even parity.', `${data.blocks.length} CODEWORDS`)}
    ${bitLegend()}
    ${stageBlocks(data.blocks, 'encode')}
    <p class="stage-note">Codeword positions: <strong>[p₁, p₂, d₁, p₃, d₂, d₃, d₄]</strong>. Parity bits are chosen so each check group has even parity.</p>
    <div class="stage-output full-width" style="margin-top: 12px"><div class="output-label"><span>TRANSMITTED HAMMING STREAM</span><span>${data.transmitted_bits.length} BITS</span></div><div class="output-value bit-text">${data.transmitted_bits}</div></div>`;
}

function renderChannelStage(data) {
  const changedCount = data.blocks.reduce((total, block) => total + block.changed_positions.length, 0);
  return `${heading(3, 'Each transmitted bit independently flips according to the selected BER.', `${data.metrics.channel_ber.toFixed(2)}% OBSERVED BER`)}
    ${bitLegend()}
    ${stageBlocks(data.blocks, 'channel')}
    <p class="stage-note">Red bits are positions that differ between the transmitted and received streams. ${changedCount ? `${changedCount} bit${changedCount === 1 ? '' : 's'} flipped in this run.` : 'No bits flipped in this run.'}</p>`;
}

function renderDecodeStage(data) {
  return `${heading(4, 'The three parity checks form S₃S₂S₁; the decimal syndrome identifies the 1-based bit to flip.', `${data.metrics.corrected_blocks} BLOCKS CORRECTED`)}
    ${bitLegend()}
    ${stageBlocks(data.blocks, 'decode')}
    <p class="stage-note">For each word: S₁ = r₁⊕r₃⊕r₅⊕r₇, S₂ = r₂⊕r₃⊕r₆⊕r₇, and S₃ = r₄⊕r₅⊕r₆⊕r₇. Positions 1, 2, and 4 are removed; positions 3, 5, 6, and 7 return the source data.</p>
    <div class="stage-output full-width" style="margin-top: 12px"><div class="output-label"><span>RECOVERED HUFFMAN BITS</span><span>${data.recovered_bits.length} BITS · PADDING REMOVED</span></div><div class="output-value bit-text">${data.recovered_bits}</div></div>`;
}

function renderOutputStage(data) {
  return `${heading(5, 'The recovered stream is traversed through the same Huffman tree used by the sender.', data.matches ? 'VERIFIED' : 'CHECK FAILED')}
    <div class="match-banner${data.matches ? '' : ' is-failed'}"><b>${data.matches ? '✓' : '!'}</b><span>${data.matches ? 'Original text exactly matches reconstructed text.' : 'The receiver output differs from the original message.'}</span></div>
    <div class="stage-columns" style="margin-top: 12px">
      ${output('ORIGINAL MESSAGE', escapeHtml(data.source_text), { pre: true })}
      ${output('RECONSTRUCTED MESSAGE', escapeHtml(data.reconstructed_text || '∅'), { pre: true })}
      ${output('FINAL SOURCE BITSTREAM', `<div class="bit-text">${data.recovered_bits}</div>`, { full: true, meta: `${data.recovered_bits.length} BITS` })}
      ${output('CHANNEL SUMMARY', `${data.metrics.corrected_blocks} corrected block${data.metrics.corrected_blocks === 1 ? '' : 's'} · ${data.metrics.channel_ber.toFixed(2)}% observed BER · ${data.metrics.channel_bits} transmitted bits`, { full: true })}
    </div>`;
}

const stageRenderers = [renderAsciiStage, renderHuffmanStage, renderHammingStage, renderChannelStage, renderDecodeStage, renderOutputStage];

function selectStage(index) {
  activeStage = Math.max(0, Math.min(stageRenderers.length - 1, index));
  if (simulationData) byId('stage-view').innerHTML = stageRenderers[activeStage](simulationData);
  document.querySelectorAll('.step-button').forEach((button) => {
    const selected = Number(button.dataset.stage) === activeStage;
    button.classList.toggle('is-active', selected);
    if (selected) button.setAttribute('aria-current', 'step');
    else button.removeAttribute('aria-current');
  });
  byId('stage-position').textContent = `STAGE ${String(activeStage + 1).padStart(2, '0')} / 06`;
  byId('previous-stage').disabled = activeStage === 0;
  byId('next-stage').disabled = activeStage === stageRenderers.length - 1;
}

function renderResults(data) {
  simulationData = data;
  const metrics = data.metrics;
  byId('metric-entropy').textContent = Number(metrics.entropy).toFixed(4);
  byId('metric-length').textContent = Number(metrics.average_code_length).toFixed(4);
  byId('metric-efficiency').innerHTML = `${Number(metrics.efficiency).toFixed(2)}<span>%</span>`;
  byId('metric-reduction').innerHTML = `${Number(metrics.compression_percent).toFixed(2)}<span>%</span>`;
  byId('metric-size').textContent = `${metrics.original_bits} → ${metrics.compressed_bits} bits`;
  byId('stream-size').textContent = `${metrics.channel_bits} BITS ON CHANNEL`;
  byId('trace-id').textContent = `RUN ${String(runNumber).padStart(3, '0')}`;
  selectStage(activeStage);
  byId('character-count').textContent = `${data.source_text.length.toLocaleString()} / 10,000`;
}

async function transmit() {
  const text = sourceText.value;
  if (!text) {
    showToast('Enter a message before transmitting.');
    sourceText.focus();
    return;
  }
  if (!/^[\x00-\x7F]*$/.test(text)) {
    showToast('This demonstration accepts 8-bit ASCII characters only.');
    sourceText.focus();
    return;
  }

  runButton.disabled = true;
  runButton.querySelector('.run-symbol').textContent = '…';
  try {
    const response = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        noise_percent: Number(noiseRate.value),
        forced_error_bit: faultToggle.checked ? Number(faultBit.value) : null
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The simulation could not be completed.');
    renderResults(data);
    runNumber += 1;
  } catch (error) {
    showToast(error.message || 'Could not reach the local simulation server.');
  } finally {
    runButton.disabled = false;
    runButton.querySelector('.run-symbol').textContent = '▶';
  }
}

function updateFaultState() {
  byId('fault-position-wrap').classList.toggle('is-hidden', !faultToggle.checked);
  faultBit.disabled = !faultToggle.checked;
}

sourceText.addEventListener('input', () => {
  byId('character-count').textContent = `${sourceText.value.length.toLocaleString()} / 10,000`;
});
noiseRate.addEventListener('input', () => {
  byId('noise-output').textContent = `${Number(noiseRate.value).toFixed(1)}%`;
});
faultToggle.addEventListener('change', updateFaultState);
runButton.addEventListener('click', transmit);
sourceText.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') transmit();
});
document.querySelectorAll('.step-button').forEach((button) => {
  button.addEventListener('click', () => selectStage(Number(button.dataset.stage)));
});
byId('previous-stage').addEventListener('click', () => selectStage(activeStage - 1));
byId('next-stage').addEventListener('click', () => selectStage(activeStage + 1));
byId('load-example').addEventListener('click', () => {
  sourceText.value = 'DATA';
  byId('character-count').textContent = '4 / 10,000';
  noiseRate.value = '0';
  byId('noise-output').textContent = '0.0%';
  faultToggle.checked = true;
  faultBit.value = '6';
  updateFaultState();
  transmit();
});
byId('file-input').addEventListener('change', async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  if (file.size > 100_000) {
    showToast('Choose a text file smaller than 100 KB.');
    event.target.value = '';
    return;
  }
  sourceText.value = await file.text();
  byId('character-count').textContent = `${sourceText.value.length.toLocaleString()} / 10,000`;
  event.target.value = '';
});

selectStage(activeStage);
updateFaultState();
transmit();
