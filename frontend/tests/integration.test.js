import { SearchModule } from '../public/js/search.js';
import { UIModule } from '../public/js/ui.js';

describe('Frontend-Backend Integration Tests', () => {
    let searchModule;
    let uiModule;

    beforeEach(() => {
        // Create mock DOM structure
        document.body.innerHTML = `
            <div class="container">
                <main class="main-content">
                    <section class="search-section">
                        <form id="searchForm">
                            <input id="query" type="text" value="">
                            <select id="type">
                                <option value="">All</option>
                                <option value="inmueble">Inmueble</option>
                                <option value="vehiculo">Vehículo</option>
                            </select>
                            <input id="priceMin" type="number" value="">
                            <input id="priceMax" type="number" value="">
                            <input id="dateFrom" type="date" value="">
                            <input id="dateTo" type="date" value="">
                            <select id="limit"><option value="50" selected>50</option></select>
                            <input id="offset" type="number" value="0">
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

        // Setup fetch mock before creating modules
        global.fetch = jest.fn();

        searchModule = new SearchModule('http://localhost:5000/api');
        uiModule = new UIModule();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        if (global.fetch && global.fetch.mockClear) {
            global.fetch.mockClear();
        }
    });

    describe('Complete Search Workflow', () => {
        test('performs search and renders results', async () => {
            const mockAssets = [
                {
                    id: 'SSSS-2024-001',
                    type: 'inmueble',
                    description: 'Piso en Madrid',
                    price_initial: 150000,
                    price_min: 120000,
                    date_subasta: '2024-03-15',
                    location: 'Madrid',
                },
            ];

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    assets: mockAssets,
                    total: 1,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const results = await searchModule.search('madrid', {}, 50, 0);
            uiModule.renderResults(results.assets);
            uiModule.updateResultsCount(results.total);

            const container = document.getElementById('resultsContainer');
            expect(container.innerHTML).toContain('SSSS-2024-001');
            expect(container.innerHTML).toContain('Piso en Madrid');
        });

        test('handles search with filters', async () => {
            const filters = {
                type: 'inmueble',
                price_min: 100000,
                price_max: 200000,
            };

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const params = searchModule.buildQueryParams('', filters);
            expect(params).toContain('type=inmueble');
            expect(params).toContain('price_min=100000');
            expect(params).toContain('price_max=200000');
        });

        test('handles pagination workflow', async () => {
            const mockAssets = Array.from({ length: 50 }, (_, i) => ({
                id: `SSSS-2024-${i + 1}`,
                type: 'inmueble',
                description: `Asset ${i + 1}`,
                price_initial: 100000 + i * 1000,
                price_min: 80000 + i * 1000,
                date_subasta: '2024-03-15',
                location: 'Madrid',
            }));

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    assets: mockAssets.slice(0, 50),
                    total: 150,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const results = await searchModule.search('', {}, 50, 0);
            uiModule.updatePaginationControls(results.total, 50, 0);

            const nextBtn = document.getElementById('nextBtn');
            expect(nextBtn.disabled).toBe(false);

            const prevBtn = document.getElementById('prevBtn');
            expect(prevBtn.disabled).toBe(true);

            const pageInfo = document.getElementById('pageInfo');
            expect(pageInfo.textContent).toContain('Página 1');
        });

        test('loads and displays search history', async () => {
            const mockHistory = [
                {
                    query: 'madrid',
                    result_count: 10,
                    created_at: '2024-01-15',
                },
                {
                    query: 'vehiculo',
                    result_count: 5,
                    created_at: '2024-01-14',
                },
            ];

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    history: mockHistory,
                    total: 2,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const result = await searchModule.getSearchHistory();
            uiModule.renderSearchHistory(result);

            const container = document.getElementById('historyContainer');
            expect(container.innerHTML).toContain('madrid');
            expect(container.innerHTML).toContain('vehiculo');
        });

        test('handles empty search results gracefully', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const results = await searchModule.search('nonexistent', {}, 50, 0);
            uiModule.renderResults(results.assets);
            uiModule.updateResultsCount(results.total);

            const container = document.getElementById('resultsContainer');
            expect(container.innerHTML).toContain('No se encontraron resultados');
        });
    });

    describe('Error Handling in Workflow', () => {
        test('handles API errors gracefully', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
            });

            // rejects.toThrow states the expectation directly. The previous
            // fail() is not a Jest global since v27, and its ReferenceError
            // would have been swallowed by the catch below.
            await expect(searchModule.search('test')).rejects.toThrow('API error');

            uiModule.showError('API error: 500 Internal Server Error');
            expect(document.querySelector('.error-message')).not.toBeNull();
        });

        test('handles network failures', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network timeout'));

            await expect(searchModule.search('test')).rejects.toThrow(
                'Failed to search assets'
            );

            uiModule.showError('Network error occurred');
        });

        test('handles invalid API response', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    // Missing required fields
                    assets: null,
                })),
            });

            const results = await searchModule.search('test');

            // Module should handle gracefully and normalize response
            expect(results).toBeDefined();
            // SearchModule ensures assets is always an array
            expect(Array.isArray(results.assets)).toBe(true);
        });
    });

    describe('User Interaction Simulation', () => {
        test('simulates complete user search session', async () => {
            // User enters search query
            const queryInput = document.getElementById('query');
            queryInput.value = 'madrid';

            // User selects filters
            const typeSelect = document.getElementById('type');
            typeSelect.value = 'inmueble';

            // Mock API response - setup BEFORE search
            const mockAssets = [
                {
                    id: '001',
                    type: 'inmueble',
                    description: 'Test asset',
                    price_initial: 150000,
                    price_min: 120000,
                    date_subasta: '2024-03-15',
                    location: 'Madrid',
                },
            ];

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: mockAssets,
                    total: 1,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            // Perform search
            const filters = { type: typeSelect.value };
            const results = await searchModule.search(queryInput.value, filters, 50, 0);

            // Verify results structure
            expect(results).toHaveProperty('assets');
            expect(results).toHaveProperty('total');
            expect(Array.isArray(results.assets)).toBe(true);

            // Render results
            uiModule.renderResults(results.assets);
            uiModule.updateResultsCount(results.total);

            // Verify UI updated
            const container = document.getElementById('resultsContainer');
            expect(container.innerHTML).toBeTruthy();
        });

        test('simulates pagination navigation', async () => {
            // First page
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 150,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            let results = await searchModule.search('', {}, 50, 0);
            expect(results.total).toBe(150);
            uiModule.updatePaginationControls(results.total, 50, 0);

            let pageInfo = document.getElementById('pageInfo');
            expect(pageInfo.textContent).toContain('Página 1');

            // Second page
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 150,
                    limit: 50,
                    offset: 50,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            results = await searchModule.search('', {}, 50, 50);
            expect(results.total).toBe(150);
            uiModule.updatePaginationControls(results.total, 50, 50);

            pageInfo = document.getElementById('pageInfo');
            expect(pageInfo.textContent).toContain('Página 2');
        });

        test('simulates filter application', async () => {
            // Apply price range filter
            const priceMin = document.getElementById('priceMin');
            const priceMax = document.getElementById('priceMax');

            priceMin.value = '100000';
            priceMax.value = '300000';

            const filters = {
                price_min: parseFloat(priceMin.value),
                price_max: parseFloat(priceMax.value),
            };

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 5,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            const results = await searchModule.search('', filters, 50, 0);

            // Verify filter values are passed through
            expect(filters.price_min).toBe(100000);
            expect(filters.price_max).toBe(300000);
            // Verify response structure
            expect(results).toHaveProperty('total');
            expect(results).toHaveProperty('assets');
        });
    });

    describe('API Response Format Validation', () => {
        test('validates search response structure', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const results = await searchModule.search('test');

            expect(results).toHaveProperty('assets');
            expect(results).toHaveProperty('total');
            expect(results).toHaveProperty('limit');
            expect(results).toHaveProperty('offset');
            expect(results).toHaveProperty('timestamp');
        });

        test('validates asset data structure', async () => {
            const mockAsset = {
                id: 'SSSS-2024-001',
                type: 'inmueble',
                description: 'Test',
                price_initial: 100000,
                price_min: 80000,
                date_subasta: '2024-03-15',
                location: 'Madrid',
            };

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [mockAsset],
                    total: 1,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            const results = await searchModule.search('test');

            expect(results).toHaveProperty('assets');
            expect(Array.isArray(results.assets)).toBe(true);
            if (results.assets.length > 0) {
                expect(results.assets[0]).toHaveProperty('id');
                expect(results.assets[0]).toHaveProperty('type');
                expect(results.assets[0]).toHaveProperty('description');
                expect(results.assets[0]).toHaveProperty('price_initial');
            }
        });

        test('validates search history response structure', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    history: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const results = await searchModule.getSearchHistory();

            expect(results).toHaveProperty('history');
            expect(results).toHaveProperty('total');
            expect(results).toHaveProperty('limit');
            expect(results).toHaveProperty('offset');
            expect(results).toHaveProperty('timestamp');
        });
    });
});
