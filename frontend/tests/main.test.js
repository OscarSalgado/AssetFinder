import { SearchModule } from '../public/js/search.js';
import { UIModule } from '../public/js/ui.js';
import { App } from '../public/js/main.js';

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

describe('App Class Tests', () => {
    beforeEach(() => {
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
                        <div id="paginationControls" style="display: none;">
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

        global.fetch.mockClear();
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('App can be instantiated and initialized', () => {
        const app = new App();
        expect(app).toBeDefined();
        expect(app.apiBaseUrl).toBeDefined();
        expect(app.searchModule).toBeDefined();
        expect(app.uiModule).toBeDefined();
    });

    test('App constructs correct API base URL', () => {
        const app = new App();
        expect(app.apiBaseUrl).toContain('/api');
    });

    test('getFiltersFromForm collects all filters', () => {
        const app = new App();
        document.getElementById('type').value = 'inmueble';
        document.getElementById('priceMin').value = '50000';
        document.getElementById('priceMax').value = '200000';
        document.getElementById('dateFrom').value = '2024-01-01';
        document.getElementById('dateTo').value = '2024-12-31';

        const filters = app.getFiltersFromForm();

        expect(filters.type).toBe('inmueble');
        expect(filters.price_min).toBe(50000);
        expect(filters.price_max).toBe(200000);
        expect(filters.date_from).toBe('2024-01-01');
        expect(filters.date_to).toBe('2024-12-31');
    });

    test('getFiltersFromForm returns empty object when no filters selected', () => {
        const app = new App();

        const filters = app.getFiltersFromForm();

        expect(Object.keys(filters).length).toBe(0);
    });

    test('getFiltersFromForm only includes non-empty filters', () => {
        const app = new App();
        const typeSelect = document.getElementById('type');
        typeSelect.innerHTML = '<option value="">All</option><option value="vehiculo">Vehículo</option>';
        typeSelect.value = 'vehiculo';
        document.getElementById('priceMin').value = '';
        document.getElementById('priceMax').value = '';

        const filters = app.getFiltersFromForm();

        expect(filters.type).toBe('vehiculo');
        expect(filters.price_min).toBeUndefined();
        expect(filters.price_max).toBeUndefined();
    });

    test('handleSearch submits form and resets pagination', async () => {
        const app = new App();
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                assets: [],
                total: 0,
                limit: 50,
                offset: 0,
                sort_by: 'date_subasta',
                sort_order: 'DESC',
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });

        document.getElementById('query').value = 'test';
        app.currentPage = 5;

        const form = document.getElementById('searchForm');
        const event = new Event('submit');
        event.preventDefault = jest.fn();

        await app.handleSearch(event);

        expect(event.preventDefault).toHaveBeenCalled();
        expect(app.currentPage).toBe(0);
        expect(app.lastSearchQuery).toBe('test');
    });

    test('performSearch updates UI with results', async () => {
        const app = new App();
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                assets: [
                    {
                        id: '001',
                        type: 'inmueble',
                        description: 'Test asset',
                        price_initial: 100000,
                        price_min: 80000,
                        date_subasta: '2024-03-15',
                        location: 'Madrid',
                    },
                ],
                total: 1,
                limit: 50,
                offset: 0,
                sort_by: 'date_subasta',
                sort_order: 'DESC',
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });

        const initialDisplay = document.getElementById('resultsContainer').innerHTML;

        await app.performSearch('test', {});

        const finalDisplay = document.getElementById('resultsContainer').innerHTML;
        expect(finalDisplay).not.toEqual(initialDisplay);
    });

    test('previousPage navigates to previous page', async () => {
        window.scrollTo = jest.fn();
        const app = new App();
        app.currentPage = 2;
        app.lastSearchQuery = 'test';
        app.lastSearchFilters = {};

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                assets: [],
                total: 100,
                limit: 50,
                offset: 0,
                sort_by: 'date_subasta',
                sort_order: 'DESC',
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });

        await app.previousPage();

        expect(app.currentPage).toBe(1);
        expect(window.scrollTo).toHaveBeenCalled();
    });

    test('previousPage does not navigate before first page', async () => {
        const app = new App();
        app.currentPage = 0;
        app.lastSearchQuery = 'test';
        app.lastSearchFilters = {};

        await app.previousPage();

        expect(app.currentPage).toBe(0);
        expect(global.fetch).not.toHaveBeenCalled();
    });

    test('nextPage navigates to next page', async () => {
        window.scrollTo = jest.fn();
        const app = new App();
        app.currentPage = 0;
        app.lastSearchQuery = 'test';
        app.lastSearchFilters = {};

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                assets: [],
                total: 100,
                limit: 50,
                offset: 0,
                sort_by: 'date_subasta',
                sort_order: 'DESC',
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });

        await app.nextPage();

        expect(app.currentPage).toBe(1);
        expect(window.scrollTo).toHaveBeenCalled();
    });

    test('loadSearchHistory handles fetch errors gracefully', async () => {
        const app = new App();
        global.fetch.mockRejectedValueOnce(new Error('Network error'));

        const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

        await app.loadSearchHistory();

        expect(consoleWarnSpy).toHaveBeenCalled();
        consoleWarnSpy.mockRestore();
    });

    test('performSearch handles API errors', async () => {
        const app = new App();
        global.fetch.mockResolvedValueOnce({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error',
        });

        const uiSpyError = jest.spyOn(app.uiModule, 'showError');
        const uiSpyLoading = jest.spyOn(app.uiModule, 'showLoading');

        await app.performSearch('test', {});

        expect(uiSpyError).toHaveBeenCalled();
        expect(uiSpyLoading).toHaveBeenCalledWith(false);

        uiSpyError.mockRestore();
        uiSpyLoading.mockRestore();
    });

    test('setupEventListeners handles missing form elements', () => {
        document.body.innerHTML = '';
        const app = new App();

        expect(() => app.setupEventListeners()).not.toThrow();
    });

    test('init loads search history on initialization', async () => {
        const app = new App();
        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                history: [{ query: 'test', result_count: 5, created_at: '2024-01-01' }],
                total: 1,
            }),
        });

        const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

        await app.loadSearchHistory();

        expect(global.fetch).toHaveBeenCalled();

        consoleWarnSpy.mockRestore();
    });

    test('previousPage scrolls to top', async () => {
        window.scrollTo = jest.fn();
        const app = new App();
        app.currentPage = 2;
        app.lastSearchQuery = 'test';
        app.lastSearchFilters = {};

        global.fetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                assets: [],
                total: 100,
                limit: 50,
                offset: 0,
                sort_by: 'date_subasta',
                sort_order: 'DESC',
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });

        await app.previousPage();

        expect(window.scrollTo).toHaveBeenCalledWith({
            top: 0,
            behavior: 'smooth',
        });
    });
});

describe('App pagination offset', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <form id="searchForm">
                <input id="query" type="text" value="">
                <select id="type"><option value="" selected></option></select>
                <input id="priceMin" type="number" value="">
                <input id="priceMax" type="number" value="">
                <input id="dateFrom" type="date" value="">
                <input id="dateTo" type="date" value="">
                <select id="limit"><option value="50" selected>50</option></select>
            </form>
            <section class="results-section">
                <div id="resultsContainer"></div>
                <div id="resultsCount"></div>
                <div id="loadingIndicator"></div>
                <div id="paginationControls">
                    <button id="prevBtn"></button>
                    <button id="nextBtn"></button>
                    <span id="pageInfo"></span>
                </div>
            </section>
        `;
        global.fetch = jest.fn();
        window.scrollTo = jest.fn();
    });

    function mockPage(total) {
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                assets: [],
                total,
                limit: 50,
                offset: 0,
                sort_by: 'date_subasta',
                sort_order: 'DESC',
                timestamp: '2024-01-01T00:00:00Z',
            }),
        });
    }

    test('currentOffset is derived from page and limit', () => {
        const app = new App();
        app.currentLimit = 50;

        app.currentPage = 0;
        expect(app.currentOffset).toBe(0);

        app.currentPage = 3;
        expect(app.currentOffset).toBe(150);
    });

    test('page 2 requests offset=limit, not offset=1', async () => {
        mockPage(500);
        const app = new App();
        app.currentLimit = 50;
        app.currentPage = 1;

        await app.performSearch('piso', {});

        const requestedUrl = global.fetch.mock.calls[0][0];
        expect(requestedUrl).toContain('offset=50');
        expect(requestedUrl).not.toContain('offset=1&');
    });

    test('pagination controls receive the record offset', async () => {
        mockPage(500);
        const app = new App();
        app.currentLimit = 50;
        app.currentPage = 2;
        const spy = jest.spyOn(app.uiModule, 'updatePaginationControls');

        await app.performSearch('piso', {});

        expect(spy).toHaveBeenCalledWith(500, 50, 100);
    });

    test('page info reflects the real page number', async () => {
        mockPage(500);
        const app = new App();
        app.currentLimit = 50;
        app.currentPage = 4;

        await app.performSearch('piso', {});

        expect(document.getElementById('pageInfo').textContent).toBe('Página 5 de 10');
    });

    test('nextPage does not advance past the last page', async () => {
        mockPage(100);
        const app = new App();
        app.currentLimit = 50;
        app.lastSearchQuery = 'piso';
        app.lastSearchFilters = {};

        await app.performSearch('piso', {});
        expect(app.lastTotal).toBe(100);

        app.currentPage = 1;  // last page: offset 50 + limit 50 >= 100
        app.nextPage();

        expect(app.currentPage).toBe(1);
        expect(window.scrollTo).not.toHaveBeenCalled();
    });

    test('nextPage advances while the total is still unknown', () => {
        mockPage(500);
        const app = new App();
        app.lastSearchQuery = 'piso';
        app.lastSearchFilters = {};

        expect(app.lastTotal).toBeNull();
        app.nextPage();

        expect(app.currentPage).toBe(1);
    });

    test('handleSearch resets page and total', async () => {
        mockPage(500);
        const app = new App();
        app.currentPage = 7;
        app.lastTotal = 999;

        await app.handleSearch({ preventDefault: jest.fn() });

        expect(app.currentPage).toBe(0);
        expect(app.lastTotal).toBe(500);
    });

    test('a superseded response does not overwrite newer results', async () => {
        const app = new App();
        const renderSpy = jest.spyOn(app.uiModule, 'renderResults');

        // First search resolves late, after a second one already ran.
        let resolveFirst;
        global.fetch.mockImplementationOnce(() => new Promise((resolve) => {
            resolveFirst = resolve;
        }));

        const firstSearch = app.performSearch('vieja', {});

        mockPage(1);
        await app.performSearch('nueva', {});
        const rendersAfterSecond = renderSpy.mock.calls.length;

        resolveFirst({
            ok: true,
            json: async () => ({ assets: [{ id: 'STALE' }], total: 1 }),
        });
        await firstSearch;

        expect(renderSpy.mock.calls.length).toBe(rendersAfterSecond);
    });

    test('an aborted search does not surface an error message', async () => {
        const app = new App();
        const errorSpy = jest.spyOn(app.uiModule, 'showError');
        const abortError = new Error('aborted');
        abortError.name = 'AbortError';
        global.fetch.mockRejectedValue(abortError);

        await app.performSearch('piso', {});

        expect(errorSpy).not.toHaveBeenCalled();
    });
});
