import { SearchModule } from '../public/js/search.js';
import { UIModule } from '../public/js/ui.js';

describe('App Integration', () => {
    beforeEach(() => {
        // Create mock DOM structure
        document.body.innerHTML = `
            <div class="container">
                <header class="header">
                    <h1>AssetFinder</h1>
                </header>
                <main class="main-content">
                    <section class="search-section">
                        <form id="searchForm">
                            <input id="query" type="text" value="">
                            <select id="type">
                                <option value="">All</option>
                                <option value="inmueble">Inmueble</option>
                            </select>
                            <input id="priceMin" type="number" value="">
                            <input id="priceMax" type="number" value="">
                            <input id="dateFrom" type="date" value="">
                            <input id="dateTo" type="date" value="">
                            <select id="limit"><option value="50" selected>50</option></select>
                            <input id="offset" type="number" value="0">
                            <button type="submit">Search</button>
                            <button type="reset">Clear</button>
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
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('SearchModule and UIModule can be instantiated', () => {
        const searchModule = new SearchModule('http://localhost:5000/api');
        const uiModule = new UIModule();

        expect(searchModule).toBeDefined();
        expect(uiModule).toBeDefined();
        expect(searchModule.apiBaseUrl).toBe('http://localhost:5000/api');
    });

    test('SearchModule can build query parameters', () => {
        const searchModule = new SearchModule('http://localhost:5000/api');

        const params = searchModule.buildQueryParams('madrid', {
            type: 'inmueble',
            price_min: 100000,
            price_max: 500000,
        });

        expect(params).toContain('q=madrid');
        expect(params).toContain('type=inmueble');
        expect(params).toContain('price_min=100000');
        expect(params).toContain('price_max=500000');
    });

    test('UIModule can render results', () => {
        const uiModule = new UIModule();

        const assets = [
            {
                id: '001',
                type: 'inmueble',
                description: 'Test asset',
                price_initial: 100000,
                price_min: 80000,
                date_subasta: '2024-03-15',
                location: 'Madrid',
            },
        ];

        uiModule.renderResults(assets);

        const container = document.getElementById('resultsContainer');
        expect(container.innerHTML).toContain('001');
        expect(container.innerHTML).toContain('Test asset');
    });

    test('UIModule can update results count', () => {
        const uiModule = new UIModule();

        uiModule.updateResultsCount(10);

        const count = document.getElementById('resultsCount');
        expect(count.textContent).toContain('10');
    });

    test('UIModule can show and hide loading indicator', () => {
        const uiModule = new UIModule();

        uiModule.showLoading(true);
        let indicator = document.getElementById('loadingIndicator');
        expect(indicator.style.display).toBe('inline');

        uiModule.showLoading(false);
        expect(indicator.style.display).toBe('none');
    });

    test('UIModule can render search history', () => {
        const uiModule = new UIModule();

        const historyData = {
            history: [
                { query: 'madrid', result_count: 5, created_at: '2024-01-15' },
                { query: 'vehiculo', result_count: 3, created_at: '2024-01-14' },
            ],
            total: 2,
        };

        uiModule.renderSearchHistory(historyData);

        const container = document.getElementById('historyContainer');
        expect(container.innerHTML).toContain('madrid');
        expect(container.innerHTML).toContain('vehiculo');
    });

    test('Form inputs can be read and processed', () => {
        const query = document.getElementById('query');
        const type = document.getElementById('type');
        const priceMin = document.getElementById('priceMin');
        const priceMax = document.getElementById('priceMax');

        query.value = 'test asset';
        type.value = 'inmueble';
        priceMin.value = '50000';
        priceMax.value = '200000';

        expect(query.value).toBe('test asset');
        expect(type.value).toBe('inmueble');
        expect(priceMin.value).toBe('50000');
        expect(priceMax.value).toBe('200000');
    });

    test('Pagination controls can be updated', () => {
        const uiModule = new UIModule();

        uiModule.updatePaginationControls(100, 50, 0);

        const pageInfo = document.getElementById('pageInfo');
        expect(pageInfo.textContent).toContain('Página 1');
    });

    test('Date formatting works correctly', () => {
        const uiModule = new UIModule();

        const formatted = uiModule.formatDate('2024-03-15');
        expect(formatted).toContain('2024');
    });

    test('Price formatting works correctly', () => {
        const uiModule = new UIModule();

        const formatted = uiModule.formatPrice(150000.50);
        expect(formatted).toContain('€');
    });

    test('HTML escaping prevents XSS', () => {
        const uiModule = new UIModule();

        const escaped = uiModule.escapeHtml('<script>alert("xss")</script>');
        expect(escaped).not.toContain('<script>');
        expect(escaped).toContain('&lt;');
        expect(escaped).toContain('&gt;');
    });

    test('Error messages can be displayed', () => {
        const uiModule = new UIModule();

        uiModule.showError('Test error message');

        const errorDiv = document.querySelector('.error-message');
        expect(errorDiv).not.toBeNull();
        expect(errorDiv.textContent).toContain('Test error message');
    });

    test('Success messages can be displayed', () => {
        const uiModule = new UIModule();

        uiModule.showSuccess('Success message');

        const successDiv = document.querySelector('.success-message');
        expect(successDiv).not.toBeNull();
        expect(successDiv.textContent).toContain('Success message');
    });

    test('SearchModule can handle fetch API response', async () => {
        const searchModule = new SearchModule('http://localhost:5000/api');

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                assets: [{ id: '001', type: 'inmueble', description: 'Test' }],
                total: 1,
                limit: 50,
                offset: 0,
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });

        const result = await searchModule.search('test');

        expect(result.assets.length).toBe(1);
        expect(result.total).toBe(1);
    });

    test('SearchModule can get search history', async () => {
        const searchModule = new SearchModule('http://localhost:5000/api');

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                history: [
                    { query: 'test', result_count: 10, created_at: '2024-01-01' },
                ],
                total: 1,
                limit: 50,
                offset: 0,
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });

        const result = await searchModule.getSearchHistory();

        expect(result.history.length).toBe(1);
        expect(result.total).toBe(1);
    });
});
