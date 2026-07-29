import { UIModule } from '../public/js/ui.js';

describe('UIModule', () => {
    let uiModule;
    let container;

    beforeEach(() => {
        // Create a mock DOM structure
        document.body.innerHTML = `
            <div class="results-section">
                <div id="resultsContainer"></div>
                <div id="resultsCount"></div>
                <div id="loadingIndicator"></div>
                <div id="paginationControls">
                    <button id="prevBtn">Previous</button>
                    <button id="nextBtn">Next</button>
                    <span id="pageInfo"></span>
                </div>
            </div>
            <div id="historyContainer"></div>
        `;

        uiModule = new UIModule();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    describe('createAssetCard', () => {
        test('creates asset card with basic information', () => {
            const asset = {
                id: 'SSSS-2024-001',
                type: 'inmueble',
                description: 'Beautiful apartment in Madrid',
                price_initial: 100000,
                price_min: 80000,
                date_subasta: '2024-03-15',
                location: 'Madrid, España',
            };

            const card = uiModule.createAssetCard(asset);

            expect(card).toContain('SSSS-2024-001');
            expect(card).toContain('inmueble');
            expect(card).toContain('Beautiful apartment in Madrid');
            expect(card).toContain('100.000,00');
        });

        test('truncates long descriptions', () => {
            const asset = {
                id: 'TEST-001',
                type: 'vehiculo',
                description: 'A'.repeat(300),
                price_initial: 50000,
                price_min: 40000,
                date_subasta: '2024-03-15',
                location: 'Test',
            };

            const card = uiModule.createAssetCard(asset);

            expect(card).toContain('...');
        });

        test('handles missing location', () => {
            const asset = {
                id: 'TEST-001',
                type: 'mueble',
                description: 'Test item',
                price_initial: 1000,
                price_min: null,
                date_subasta: '2024-03-15',
                location: null,
            };

            const card = uiModule.createAssetCard(asset);

            expect(card).toContain('No especificado');
        });

        test('handles missing price_min', () => {
            const asset = {
                id: 'TEST-001',
                type: 'otros',
                description: 'Test',
                price_initial: 5000,
                price_min: null,
                date_subasta: '2024-03-15',
                location: 'Test',
            };

            const card = uiModule.createAssetCard(asset);

            expect(card).toContain('N/A');
        });

        test('escapes HTML in asset data', () => {
            const asset = {
                id: 'TEST-<script>alert("xss")</script>',
                type: 'inmueble',
                description: '<img src=x onerror=alert("xss")>',
                price_initial: 100000,
                price_min: 80000,
                date_subasta: '2024-03-15',
                location: 'Test & Location',
            };

            const card = uiModule.createAssetCard(asset);

            expect(card).toContain('&lt;script&gt;');
            expect(card).toContain('&lt;img');
            expect(card).toContain('&amp;');
        });
    });

    describe('renderResults', () => {
        test('renders multiple asset cards', () => {
            const assets = [
                {
                    id: '001',
                    type: 'inmueble',
                    description: 'Asset 1',
                    price_initial: 100000,
                    price_min: 80000,
                    date_subasta: '2024-03-15',
                    location: 'Madrid',
                },
                {
                    id: '002',
                    type: 'vehiculo',
                    description: 'Asset 2',
                    price_initial: 50000,
                    price_min: 40000,
                    date_subasta: '2024-03-16',
                    location: 'Barcelona',
                },
            ];

            uiModule.renderResults(assets);

            expect(uiModule.resultsContainer.innerHTML).toContain('001');
            expect(uiModule.resultsContainer.innerHTML).toContain('002');
            expect(uiModule.resultsContainer.innerHTML).toContain('Asset 1');
            expect(uiModule.resultsContainer.innerHTML).toContain('Asset 2');
        });

        test('shows empty state when no results', () => {
            uiModule.renderResults([]);

            expect(uiModule.resultsContainer.innerHTML).toContain('No se encontraron resultados');
        });

        test('shows empty state when null results', () => {
            uiModule.renderResults(null);

            expect(uiModule.resultsContainer.innerHTML).toContain('No se encontraron resultados');
        });
    });

    describe('updateResultsCount', () => {
        test('updates result count with singular form', () => {
            uiModule.updateResultsCount(1);

            expect(uiModule.resultsCount.textContent).toBe('1 resultado');
        });

        test('updates result count with plural form', () => {
            uiModule.updateResultsCount(5);

            expect(uiModule.resultsCount.textContent).toBe('5 resultados');
        });

        test('updates result count with zero', () => {
            uiModule.updateResultsCount(0);

            expect(uiModule.resultsCount.textContent).toBe('0 resultados');
        });
    });

    describe('updatePaginationControls', () => {
        test('hides pagination when no results', () => {
            uiModule.updatePaginationControls(0, 50, 0);

            expect(uiModule.paginationControls.style.display).toBe('none');
        });

        test('hides pagination when results fit in one page', () => {
            uiModule.updatePaginationControls(25, 50, 0);

            expect(uiModule.paginationControls.style.display).toBe('none');
        });

        test('shows pagination when results span multiple pages', () => {
            uiModule.updatePaginationControls(100, 50, 0);

            expect(uiModule.paginationControls.style.display).toBe('flex');
        });

        test('disables previous button on first page', () => {
            const prevBtn = document.getElementById('prevBtn');
            uiModule.updatePaginationControls(100, 50, 0);

            expect(prevBtn.disabled).toBe(true);
        });

        test('enables previous button on later pages', () => {
            const prevBtn = document.getElementById('prevBtn');
            uiModule.updatePaginationControls(100, 50, 50);

            expect(prevBtn.disabled).toBe(false);
        });

        test('disables next button on last page', () => {
            const nextBtn = document.getElementById('nextBtn');
            uiModule.updatePaginationControls(100, 50, 50);

            expect(nextBtn.disabled).toBe(true);
        });

        test('enables next button when more pages available', () => {
            const nextBtn = document.getElementById('nextBtn');
            uiModule.updatePaginationControls(200, 50, 0);

            expect(nextBtn.disabled).toBe(false);
        });

        test('updates page info correctly', () => {
            const pageInfo = document.getElementById('pageInfo');
            uiModule.updatePaginationControls(150, 50, 50);

            expect(pageInfo.textContent).toBe('Página 2 de 3');
        });
    });

    describe('formatPrice', () => {
        test('formats price with commas and decimals', () => {
            const formatted = uiModule.formatPrice(100000);

            expect(formatted).toContain('100');
            expect(formatted).toContain('000');
        });

        test('returns 0 for missing price', () => {
            const formatted = uiModule.formatPrice(null);

            expect(formatted).toBe('€ 0,00');
        });

        test('returns 0 for zero price', () => {
            const formatted = uiModule.formatPrice(0);

            expect(formatted).toBe('€ 0,00');
        });
    });

    describe('formatDate', () => {
        test('formats valid date in Spanish locale', () => {
            const formatted = uiModule.formatDate('2024-03-15');

            expect(formatted).toContain('2024');
            expect(formatted).toContain('15');
        });

        test('returns N/A for missing date', () => {
            const formatted = uiModule.formatDate(null);

            expect(formatted).toBe('N/A');
        });

        test('returns string for invalid date format', () => {
            const formatted = uiModule.formatDate('invalid');

            // formatDate returns the dateString if toLocaleDateString throws
            // This happens when Date() throws or returns Invalid Date
            expect(formatted).toEqual('invalid');
        });

        test('handles empty string date', () => {
            const formatted = uiModule.formatDate('');

            expect(formatted).toBe('N/A');
        });

        test('handles various date formats', () => {
            const formatted1 = uiModule.formatDate('2024-01-01');
            const formatted2 = uiModule.formatDate('2024-12-31');

            expect(formatted1).toContain('2024');
            expect(formatted2).toContain('2024');
        });

        test('handles date formatting exception', () => {
            // formatDate uses a cached Intl.DateTimeFormat, so the failure has to
            // be injected into the formatter itself rather than into Date.
            // `format` is an accessor on the prototype, hence defineProperty.
            const descriptor = Object.getOwnPropertyDescriptor(
                Intl.DateTimeFormat.prototype,
                'format'
            );
            Object.defineProperty(Intl.DateTimeFormat.prototype, 'format', {
                configurable: true,
                get() {
                    return () => {
                        throw new Error('Locale error');
                    };
                },
            });

            const formatted = uiModule.formatDate('2024-03-15');

            // Should return the original string when exception occurs
            expect(formatted).toBe('2024-03-15');

            // Restore original
            Object.defineProperty(Intl.DateTimeFormat.prototype, 'format', descriptor);
        });
    });

    describe('renderSearchHistory', () => {
        test('renders search history items', () => {
            const historyData = {
                history: [
                    { query: 'madrid', result_count: 10, created_at: '2024-01-15' },
                    { query: 'vehiculo', result_count: 5, created_at: '2024-01-14' },
                ],
                total: 2,
            };

            uiModule.renderSearchHistory(historyData);

            expect(uiModule.historyContainer.innerHTML).toContain('madrid');
            expect(uiModule.historyContainer.innerHTML).toContain('vehiculo');
        });

        test('shows empty state when no history', () => {
            uiModule.renderSearchHistory({ history: [], total: 0 });

            expect(uiModule.historyContainer.innerHTML).toContain('No hay búsquedas registradas');
        });

        test('handles null history', () => {
            uiModule.renderSearchHistory(null);

            expect(uiModule.historyContainer.innerHTML).toContain('No hay búsquedas registradas');
        });
    });

    describe('showLoading', () => {
        test('shows loading indicator', () => {
            uiModule.showLoading(true);

            expect(uiModule.loadingIndicator.style.display).toBe('inline');
        });

        test('hides loading indicator', () => {
            uiModule.showLoading(false);

            expect(uiModule.loadingIndicator.style.display).toBe('none');
        });
    });

    describe('showError', () => {
        test('creates and displays error message', () => {
            uiModule.showError('Test error message');

            const errorMessage = document.querySelector('.error-message');
            expect(errorMessage).not.toBeNull();
            expect(errorMessage.textContent).toContain('Test error message');
        });

        test('removes error message after timeout', (done) => {
            jest.useFakeTimers();
            uiModule.showError('Test error');

            let errorMessage = document.querySelector('.error-message');
            expect(errorMessage).not.toBeNull();

            jest.advanceTimersByTime(5100);
            errorMessage = document.querySelector('.error-message');
            expect(errorMessage).toBeNull();

            jest.useRealTimers();
            done();
        });
    });

    describe('showSuccess', () => {
        test('creates and displays success message', () => {
            uiModule.showSuccess('Test success message');

            const successMessage = document.querySelector('.success-message');
            expect(successMessage).not.toBeNull();
            expect(successMessage.textContent).toContain('Test success message');
        });

        test('removes success message after timeout', (done) => {
            jest.useFakeTimers();
            uiModule.showSuccess('Test success');

            let successMessage = document.querySelector('.success-message');
            expect(successMessage).not.toBeNull();

            jest.advanceTimersByTime(5100);
            successMessage = document.querySelector('.success-message');
            expect(successMessage).toBeNull();

            jest.useRealTimers();
            done();
        });
    });

    describe('escapeHtml', () => {
        test('escapes HTML tags', () => {
            const escaped = uiModule.escapeHtml('<script>alert("xss")</script>');

            expect(escaped).not.toContain('<script>');
            expect(escaped).toContain('&lt;');
            expect(escaped).toContain('&gt;');
        });

        test('escapes ampersands', () => {
            const escaped = uiModule.escapeHtml('Test & Test');

            expect(escaped).toContain('&amp;');
        });

        test('returns empty string for null', () => {
            const escaped = uiModule.escapeHtml(null);

            expect(escaped).toBe('');
        });
    });

    describe('Branch Coverage Tests', () => {
        test('renderResults returns early when resultsContainer is null', () => {
            const uiModuleNoContainer = new UIModule();
            uiModuleNoContainer.resultsContainer = null;

            const assets = [{ id: '1', type: 'inmueble', description: 'Test', price_initial: 100, date_subasta: '2024-01-01', location: 'Test' }];
            uiModuleNoContainer.renderResults(assets);

            expect(uiModuleNoContainer.resultsContainer).toBeNull();
        });

        test('updateResultsCount returns early when resultsCount is null', () => {
            const uiModuleNoCount = new UIModule();
            uiModuleNoCount.resultsCount = null;

            uiModuleNoCount.updateResultsCount(5);
            expect(uiModuleNoCount.resultsCount).toBeNull();
        });

        test('updatePaginationControls returns early when paginationControls is null', () => {
            const uiModuleNoPagination = new UIModule();
            uiModuleNoPagination.paginationControls = null;

            uiModuleNoPagination.updatePaginationControls(100, 50, 0);
            expect(uiModuleNoPagination.paginationControls).toBeNull();
        });

        test('updatePaginationControls handles missing prevBtn', () => {
            const uiModuleNoPrevBtn = new UIModule();
            document.body.innerHTML = `
                <div id="paginationControls">
                    <button id="nextBtn">Next</button>
                    <span id="pageInfo"></span>
                </div>
            `;
            uiModuleNoPrevBtn.paginationControls = document.getElementById('paginationControls');

            uiModuleNoPrevBtn.updatePaginationControls(100, 50, 0);
            expect(uiModuleNoPrevBtn.paginationControls.style.display).toBe('flex');
        });

        test('updatePaginationControls handles missing nextBtn', () => {
            const uiModuleNoNextBtn = new UIModule();
            document.body.innerHTML = `
                <div id="paginationControls">
                    <button id="prevBtn">Prev</button>
                    <span id="pageInfo"></span>
                </div>
            `;
            uiModuleNoNextBtn.paginationControls = document.getElementById('paginationControls');

            uiModuleNoNextBtn.updatePaginationControls(100, 50, 0);
            expect(uiModuleNoNextBtn.paginationControls.style.display).toBe('flex');
        });

        test('updatePaginationControls handles missing pageInfo', () => {
            const uiModuleNoPageInfo = new UIModule();
            document.body.innerHTML = `
                <div id="paginationControls">
                    <button id="prevBtn">Prev</button>
                    <button id="nextBtn">Next</button>
                </div>
            `;
            uiModuleNoPageInfo.paginationControls = document.getElementById('paginationControls');

            uiModuleNoPageInfo.updatePaginationControls(100, 50, 0);
            expect(uiModuleNoPageInfo.paginationControls.style.display).toBe('flex');
        });

        test('renderSearchHistory returns early when historyContainer is null', () => {
            const uiModuleNoHistory = new UIModule();
            uiModuleNoHistory.historyContainer = null;

            const historyData = { history: [{ query: 'test', result_count: 5, created_at: '2024-01-01' }] };
            uiModuleNoHistory.renderSearchHistory(historyData);

            expect(uiModuleNoHistory.historyContainer).toBeNull();
        });

        test('showError returns when results section is missing', () => {
            document.body.innerHTML = '';
            const uiModuleNoSection = new UIModule();

            uiModuleNoSection.showError('Test error');

            const errorMessage = document.querySelector('.error-message');
            expect(errorMessage).toBeNull();
        });

        test('showSuccess returns when results section is missing', () => {
            document.body.innerHTML = '';
            const uiModuleNoSection = new UIModule();

            uiModuleNoSection.showSuccess('Test success');

            const successMessage = document.querySelector('.success-message');
            expect(successMessage).toBeNull();
        });

        test('formatDate returns original string when Date is invalid but substring works', () => {
            const formatted = uiModule.formatDate('not-a-date');
            expect(formatted).toBe('not-a-date');
        });

        test('escapeHtml returns empty string for undefined', () => {
            const escaped = uiModule.escapeHtml(undefined);
            expect(escaped).toBe('');
        });

        test('createAssetCard handles empty description', () => {
            const asset = {
                id: 'TEST-001',
                type: 'inmueble',
                description: '',
                price_initial: 100000,
                price_min: 80000,
                date_subasta: '2024-03-15',
                location: 'Madrid',
            };

            const card = uiModule.createAssetCard(asset);
            expect(card).toContain('TEST-001');
            expect(card).toContain('asset-card');
        });

        test('getAssetTypeBadge returns original type for unknown types', () => {
            const badge = uiModule.getAssetTypeBadge('unknown_type');
            expect(badge).toBe('unknown_type');
        });
    });
});

describe('UIModule escapeHtml attribute safety', () => {
    let uiModule;

    beforeEach(() => {
        document.body.innerHTML = `
            <div id="resultsContainer"></div>
            <div id="resultsCount"></div>
            <div id="loadingIndicator"></div>
            <div id="paginationControls"></div>
            <div id="historyContainer"></div>
        `;
        uiModule = new UIModule();
    });

    test('escapes the five HTML-significant characters', () => {
        expect(uiModule.escapeHtml('&')).toBe('&amp;');
        expect(uiModule.escapeHtml('<')).toBe('&lt;');
        expect(uiModule.escapeHtml('>')).toBe('&gt;');
        expect(uiModule.escapeHtml('"')).toBe('&quot;');
        expect(uiModule.escapeHtml("'")).toBe('&#39;');
    });

    test('escapes quotes so attribute values cannot be broken out of', () => {
        // escapeHtml output is interpolated into data-asset-id and class
        // attributes, so unescaped quotes would allow attribute injection.
        const payload = 'x" onmouseover="alert(1)';

        expect(uiModule.escapeHtml(payload)).not.toContain('"');
    });

    test('a malicious asset id does not inject an attribute into the card', () => {
        uiModule.renderResults([
            {
                id: 'x" onmouseover="alert(1)',
                type: 'inmueble',
                description: 'Piso en Madrid',
                price_initial: 1000,
                price_min: 900,
                date_subasta: '2024-03-15',
                location: 'Madrid',
            },
        ]);

        const card = document.querySelector('.asset-card');
        expect(card.hasAttribute('onmouseover')).toBe(false);
        expect(card.getAttribute('data-asset-id')).toBe('x" onmouseover="alert(1)');
    });

    test('script tags in descriptions are rendered inert', () => {
        uiModule.renderResults([
            {
                id: 'SAFE-1',
                type: 'inmueble',
                description: '<script>alert(1)</script>',
                price_initial: 1000,
                price_min: 900,
                date_subasta: '2024-03-15',
                location: 'Madrid',
            },
        ]);

        expect(document.querySelector('#resultsContainer script')).toBeNull();
    });

    test('returns an empty string for falsy input', () => {
        expect(uiModule.escapeHtml('')).toBe('');
        expect(uiModule.escapeHtml(null)).toBe('');
        expect(uiModule.escapeHtml(undefined)).toBe('');
    });

    test('leaves ordinary text untouched', () => {
        expect(uiModule.escapeHtml('Piso en Madrid centro')).toBe('Piso en Madrid centro');
    });
});
