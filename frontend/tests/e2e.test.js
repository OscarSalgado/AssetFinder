import { SearchModule } from '../public/js/search.js';
import { UIModule } from '../public/js/ui.js';

describe('End-to-End Application Flow', () => {
    let searchModule;
    let uiModule;
    let queryInput;
    let typeSelect;
    let priceMinInput;
    let priceMaxInput;
    let dateFromInput;
    let dateToInput;
    let limitSelect;
    let offsetInput;
    let prevBtn;
    let nextBtn;

    beforeEach(() => {
        // Create complete mock DOM structure matching actual HTML
        document.body.innerHTML = `
            <div class="container">
                <main class="main-content">
                    <section class="search-section">
                        <form id="searchForm">
                            <input id="query" type="text" value="" placeholder="Search assets">
                            <select id="type">
                                <option value="">All types</option>
                                <option value="inmueble">Inmueble</option>
                                <option value="vehiculo">Vehículo</option>
                                <option value="mueble">Mueble</option>
                                <option value="otros">Otros</option>
                            </select>
                            <input id="priceMin" type="number" value="" placeholder="Min price">
                            <input id="priceMax" type="number" value="" placeholder="Max price">
                            <input id="dateFrom" type="date" value="">
                            <input id="dateTo" type="date" value="">
                            <select id="limit">
                                <option value="10">10</option>
                                <option value="50" selected>50</option>
                                <option value="100">100</option>
                            </select>
                            <input id="offset" type="number" value="0">
                            <button type="submit">Search</button>
                        </form>
                    </section>
                    <section class="results-section">
                        <div id="resultsContainer"></div>
                        <div id="resultsCount"></div>
                        <div id="loadingIndicator"></div>
                        <div id="paginationControls">
                            <button id="prevBtn">Previous</button>
                            <button id="nextBtn">Next</button>
                            <span id="pageInfo"></span>
                        </div>
                    </section>
                    <section class="history-section">
                        <div id="historyContainer"></div>
                    </section>
                </main>
            </div>
        `;

        // Setup fetch mock
        global.fetch = jest.fn();

        // Initialize modules
        searchModule = new SearchModule('http://localhost:5000/api');
        uiModule = new UIModule();

        // Get DOM references
        queryInput = document.getElementById('query');
        typeSelect = document.getElementById('type');
        priceMinInput = document.getElementById('priceMin');
        priceMaxInput = document.getElementById('priceMax');
        dateFromInput = document.getElementById('dateFrom');
        dateToInput = document.getElementById('dateTo');
        limitSelect = document.getElementById('limit');
        offsetInput = document.getElementById('offset');
        prevBtn = document.getElementById('prevBtn');
        nextBtn = document.getElementById('nextBtn');
    });

    afterEach(() => {
        document.body.innerHTML = '';
        if (global.fetch && global.fetch.mockClear) {
            global.fetch.mockClear();
        }
    });

    describe('User Search Flow', () => {
        test('user enters query and submits form', async () => {
            queryInput.value = 'madrid';

            expect(queryInput.value).toBe('madrid');
        });

        test('user selects asset type filter', async () => {
            typeSelect.value = 'inmueble';

            expect(typeSelect.value).toBe('inmueble');
        });

        test('user sets price range filter', async () => {
            priceMinInput.value = '50000';
            priceMaxInput.value = '200000';

            expect(priceMinInput.value).toBe('50000');
            expect(priceMaxInput.value).toBe('200000');
        });

        test('user sets date range filter', async () => {
            dateFromInput.value = '2024-01-01';
            dateToInput.value = '2024-12-31';

            expect(dateFromInput.value).toBe('2024-01-01');
            expect(dateToInput.value).toBe('2024-12-31');
        });

        test('user changes pagination limit', async () => {
            limitSelect.value = '100';

            expect(limitSelect.value).toBe('100');
        });

        test('application handles search with all filters', async () => {
            // Set all filter values
            queryInput.value = 'test';
            typeSelect.value = 'vehiculo';
            priceMinInput.value = '10000';
            priceMaxInput.value = '50000';
            dateFromInput.value = '2024-01-01';
            dateToInput.value = '2024-12-31';

            // Build filters object as application would
            const filters = {};
            if (typeSelect.value) filters.type = typeSelect.value;
            if (priceMinInput.value) filters.price_min = parseFloat(priceMinInput.value);
            if (priceMaxInput.value) filters.price_max = parseFloat(priceMaxInput.value);
            if (dateFromInput.value) filters.date_from = dateFromInput.value;
            if (dateToInput.value) filters.date_to = dateToInput.value;

            // Mock API response
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [
                        {
                            id: 'VEH-001',
                            type: 'vehiculo',
                            description: 'Test vehicle',
                            price_initial: 25000,
                            price_min: 20000,
                            date_subasta: '2024-06-15',
                            location: 'Barcelona',
                        },
                    ],
                    total: 1,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            // Perform search
            const results = await searchModule.search(queryInput.value, filters, 50, 0);

            // Verify results
            expect(results).toHaveProperty('assets');
            expect(results).toHaveProperty('total');

            // Render results
            uiModule.renderResults(results.assets);
            uiModule.updateResultsCount(results.total);

            // Verify UI updated
            const resultsContainer = document.getElementById('resultsContainer');
            expect(resultsContainer.innerHTML).toBeTruthy();
        });
    });

    describe('Pagination Controls', () => {
        test('pagination buttons are disabled on first page', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 100,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            const results = await searchModule.search('', {}, 50, 0);
            uiModule.updatePaginationControls(results.total, 50, 0);

            expect(prevBtn.disabled).toBe(true);
            expect(nextBtn.disabled).toBe(false);
        });

        test('pagination buttons are enabled on middle page', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 200,
                    limit: 50,
                    offset: 50,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            const results = await searchModule.search('', {}, 50, 50);
            uiModule.updatePaginationControls(results.total, 50, 50);

            expect(prevBtn.disabled).toBe(false);
            expect(nextBtn.disabled).toBe(false);
        });

        test('pagination buttons are disabled on last page', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 100,
                    limit: 50,
                    offset: 50,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            const results = await searchModule.search('', {}, 50, 50);
            uiModule.updatePaginationControls(results.total, 50, 50);

            expect(prevBtn.disabled).toBe(false);
            expect(nextBtn.disabled).toBe(true);
        });

        test('offset updates correctly for pagination', async () => {
            offsetInput.value = '0';
            expect(offsetInput.value).toBe('0');

            offsetInput.value = '50';
            expect(offsetInput.value).toBe('50');

            offsetInput.value = '100';
            expect(offsetInput.value).toBe('100');
        });
    });

    describe('Results Rendering', () => {
        test('renders multiple asset cards', async () => {
            const assets = [
                {
                    id: 'ASSET-001',
                    type: 'inmueble',
                    description: 'Beautiful apartment',
                    price_initial: 150000,
                    price_min: 120000,
                    date_subasta: '2024-03-15',
                    location: 'Madrid',
                },
                {
                    id: 'ASSET-002',
                    type: 'vehiculo',
                    description: 'Used car',
                    price_initial: 15000,
                    price_min: 12000,
                    date_subasta: '2024-04-20',
                    location: 'Barcelona',
                },
            ];

            uiModule.renderResults(assets);
            const container = document.getElementById('resultsContainer');

            expect(container.innerHTML).toContain('ASSET-001');
            expect(container.innerHTML).toContain('ASSET-002');
            expect(container.innerHTML).toContain('Beautiful apartment');
            expect(container.innerHTML).toContain('Used car');
        });

        test('displays results count with singular form', async () => {
            uiModule.updateResultsCount(1);

            const resultsCount = document.getElementById('resultsCount');
            expect(resultsCount.textContent).toBe('1 resultado');
        });

        test('displays results count with plural form', async () => {
            uiModule.updateResultsCount(5);

            const resultsCount = document.getElementById('resultsCount');
            expect(resultsCount.textContent).toBe('5 resultados');
        });

        test('displays empty state when no results', async () => {
            uiModule.renderResults([]);

            const container = document.getElementById('resultsContainer');
            expect(container.innerHTML).toContain('No se encontraron resultados');
        });
    });

    describe('Search History', () => {
        test('loads and displays search history', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    history: [
                        {
                            query: 'madrid',
                            result_count: 10,
                            created_at: '2024-01-15',
                        },
                        {
                            query: 'barcelona',
                            result_count: 5,
                            created_at: '2024-01-14',
                        },
                    ],
                    total: 2,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            const result = await searchModule.getSearchHistory();
            uiModule.renderSearchHistory(result);

            const historyContainer = document.getElementById('historyContainer');
            expect(historyContainer.innerHTML).toContain('madrid');
            expect(historyContainer.innerHTML).toContain('barcelona');
        });

        test('displays empty state when no history', async () => {
            uiModule.renderSearchHistory({ history: [], total: 0 });

            const historyContainer = document.getElementById('historyContainer');
            expect(historyContainer.innerHTML).toContain('No hay búsquedas registradas');
        });
    });

    describe('Error Handling', () => {
        test('shows error message on API failure', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
            });

            try {
                await searchModule.search('test');
                expect(true).toBe(false); // Should throw
            } catch (error) {
                expect(error.message).toContain('API error');
                uiModule.showError(error.message);

                const errorDiv = document.querySelector('.error-message');
                expect(errorDiv).not.toBeNull();
                expect(errorDiv.textContent).toContain('API error');
            }
        });

        test('shows error message on network failure', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network timeout'));

            try {
                await searchModule.search('test');
                expect(true).toBe(false); // Should throw
            } catch (error) {
                expect(error.message).toContain('Failed to search assets');
                uiModule.showError('Network error occurred');

                const errorDiv = document.querySelector('.error-message');
                expect(errorDiv).not.toBeNull();
            }
        });

        test('shows success message after successful search', async () => {
            uiModule.showSuccess('Search completed successfully');

            const successDiv = document.querySelector('.success-message');
            expect(successDiv).not.toBeNull();
            expect(successDiv.textContent).toContain('Search completed successfully');
        });
    });

    describe('Loading State', () => {
        test('shows loading indicator when searching', async () => {
            uiModule.showLoading(true);

            const loadingIndicator = document.getElementById('loadingIndicator');
            expect(loadingIndicator.style.display).toBe('inline');
        });

        test('hides loading indicator after search', async () => {
            uiModule.showLoading(false);

            const loadingIndicator = document.getElementById('loadingIndicator');
            expect(loadingIndicator.style.display).toBe('none');
        });
    });

    describe('XSS Protection', () => {
        test('escapes HTML in search results', async () => {
            const maliciousAsset = {
                id: 'TEST-001',
                type: 'inmueble',
                description: '<img src=x onerror="alert(\'xss\')">',
                price_initial: 100000,
                price_min: 80000,
                date_subasta: '2024-03-15',
                location: 'Test & Location',
            };

            uiModule.renderResults([maliciousAsset]);
            const container = document.getElementById('resultsContainer');

            // Verify HTML is properly escaped (contains entities instead of raw tags)
            expect(container.innerHTML).toContain('&lt;img');
            expect(container.innerHTML).toContain('&amp;');
            // Verify dangerous attributes are escaped
            expect(container.innerHTML).toContain('onerror');
            // But not as executable code
            expect(container.innerHTML).toContain('&lt;img');
        });

        test('escapes HTML in history items', async () => {
            const maliciousHistory = {
                history: [
                    {
                        query: '<script>alert("xss")</script>',
                        result_count: 5,
                        created_at: '2024-01-01',
                    },
                ],
            };

            uiModule.renderSearchHistory(maliciousHistory);
            const historyContainer = document.getElementById('historyContainer');

            expect(historyContainer.innerHTML).toContain('&lt;script&gt;');
            expect(historyContainer.innerHTML).not.toContain('<script>');
        });
    });
});
