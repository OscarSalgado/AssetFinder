/**
 * Micro-benchmark del render de resultados.
 *
 * Compara la implementacion anterior (un elemento DOM por escape, un formateador
 * Intl por celda) con la actual (tabla estatica de entidades, formateadores
 * cacheados). Se ejecuta con jsdom para tener DOM real:
 *
 *     node --experimental-vm-modules bench.mjs
 *     npm run bench
 */

import { JSDOM } from 'jsdom';

const dom = new JSDOM('<!doctype html><html><body></body></html>');
global.document = dom.window.document;

const CARDS = 50;
const REPS = 200;

const assets = Array.from({ length: CARDS }, (_, i) => ({
    id: `SSSS-2024-${String(i).padStart(3, '0')}`,
    type: ['inmueble', 'vehiculo', 'mueble', 'otros'][i % 4],
    description: `Piso de ${(i % 5) + 1} habitaciones en Madrid centro con balcon & vista`,
    price_initial: 100000 + i * 137.5,
    price_min: 80000 + i * 100,
    date_subasta: '2024-03-15',
    location: 'Madrid, España',
}));

// ---------------------------------------------------------------- antes

function escapeHtmlBefore(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatPriceBefore(price) {
    if (!price || price === 0) return '€ 0,00';
    return `€ ${parseFloat(price).toLocaleString('es-ES', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
}

function formatDateBefore(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    });
}

// ---------------------------------------------------------------- despues

const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const HTML_ESCAPE_PATTERN = /[&<>"']/g;
const PRICE_FORMATTER = new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});
const DATE_FORMATTER = new Intl.DateTimeFormat('es-ES', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
});

function escapeHtmlAfter(text) {
    if (!text) return '';
    return String(text).replace(HTML_ESCAPE_PATTERN, (char) => HTML_ESCAPES[char]);
}

function formatPriceAfter(price) {
    if (!price || price === 0) return '€ 0,00';
    return `€ ${PRICE_FORMATTER.format(parseFloat(price))}`;
}

function formatDateAfter(dateString) {
    return DATE_FORMATTER.format(new Date(dateString));
}

// ------------------------------------------------------------- medicion

function renderPage(escape, formatPrice, formatDate) {
    let html = '';
    for (const asset of assets) {
        // Mismo numero de llamadas que createAssetCard: 6 escapes, 2 precios, 1 fecha.
        html += `<div data-asset-id="${escape(asset.id)}">
            <div>${escape(asset.id)}</div>
            <div class="${escape(asset.type)}">${escape(asset.type)}</div>
            <div>${escape(asset.description.substring(0, 200))}</div>
            <div>${formatPrice(asset.price_initial)}</div>
            <div>${formatPrice(asset.price_min)}</div>
            <div>${formatDate(asset.date_subasta)}</div>
            <div>${escape(asset.location)}</div>
        </div>`;
    }
    return html;
}

function measure(label, fn) {
    fn(); // calentamiento
    const samples = [];
    for (let r = 0; r < 7; r++) {
        const start = process.hrtime.bigint();
        for (let i = 0; i < REPS; i++) fn();
        samples.push(Number(process.hrtime.bigint() - start) / 1e6 / REPS);
    }
    samples.sort((a, b) => a - b);
    const median = samples[Math.floor(samples.length / 2)];
    console.log(`${label.padEnd(34)} ${median.toFixed(3).padStart(10)} ms/render`);
    return median;
}

console.log('='.repeat(60));
console.log(`Render de ${CARDS} tarjetas (mediana de ${REPS} renders x7)`);
console.log('='.repeat(60));

const before = measure('antes (DOM + Intl por celda)', () =>
    renderPage(escapeHtmlBefore, formatPriceBefore, formatDateBefore)
);
const after = measure('despues (tabla + Intl cacheado)', () =>
    renderPage(escapeHtmlAfter, formatPriceAfter, formatDateAfter)
);

console.log('-'.repeat(60));
console.log(`mejora: ${(before / after).toFixed(1)}x mas rapido`);
console.log(`elementos DOM creados por render: ${CARDS * 6} -> 0`);
console.log(`formateadores Intl por render:    ${CARDS * 3} -> 0 (2 al cargar el modulo)`);

// La version nueva escapa un superconjunto: &<> igual que antes, y ademas las
// comillas. No es una regresion sino una correccion, porque escapeHtml se
// interpola dentro de atributos (data-asset-id, class) donde textContent ->
// innerHTML dejaba pasar las comillas y permitia inyectar atributos.
const textSample = 'Piso 3 hab & <balcon> en Madrid';
if (escapeHtmlBefore(textSample) !== escapeHtmlAfter(textSample)) {
    console.error('\nATENCION: escapeHtml difiere en texto sin comillas');
    process.exitCode = 1;
} else {
    console.log('\nequivalencia verificada en texto sin comillas (& < >)');
}

const attrPayload = 'x" onmouseover="alert(1)';
const escaped = escapeHtmlAfter(attrPayload);
if (escaped.includes('"')) {
    console.error('ATENCION: las comillas no se escapan, atributo inyectable');
    process.exitCode = 1;
} else {
    console.log('comillas escapadas: atributo no inyectable');
}
