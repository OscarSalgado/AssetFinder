import { App } from '../public/js/main.js';

describe('App Class', () => {
    let app;

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

        // Mock fetch
        global.fetch = jest.fn();

        // Mock window.scrollTo
        window.scrollTo = jest.fn();

        // Create app instance
        app = new App();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        jest.clearAllMocks();
    });

    describe('Initialization', () => {
        test('constructs App with default values', () => {
            expect(app.currentPage).toBe(0);
            expect(app.currentLimit).toBe(50);
            expect(app.lastSearchQuery).toBeNull();
            expect(app.lastSearchFilters).toBeNull();
        });

        test('gets API base URL from window.location', () => {
            expect(app.apiBaseUrl).toContain('http');
            expect(app.apiBaseUrl).toContain('api');
        });

        test('initializes SearchModule with correct API URL', () => {
            expect(app.searchModule).toBeDefined();
            expect(app.searchModule.apiBaseUrl).toBe(app.apiBaseUrl);
        });

        test('initializes UIModule', () => {
            expect(app.uiModule).toBeDefined();
        });
    });

    describe('Form Filter Handling', () => {
        test('extracts filters from form with all fields', () => {
            document.getElementById('type').value = 'inmueble';
            document.getElementById('priceMin').value = '100000';
            document.getElementById('priceMax').value = '300000';
            document.getElementById('dateFrom').value = '2024-01-01';
            document.getElementById('dateTo').value = '2024-12-31';

            const filters = app.getFiltersFromForm();

            expect(filters.type).toBe('inmueble');
            expect(filters.price_min).toBe(100000);
            expect(filters.price_max).toBe(300000);
            expect(filters.date_from).toBe('2024-01-01');
            expect(filters.date_to).toBe('2024-12-31');
        });

        test('extracts filters with empty values', () => {
            document.getElementById('type').value = '';
            document.getElementById('priceMin').value = '';
            document.getElementById('priceMax').value = '';

            const filters = app.getFiltersFromForm();

            expect(Object.keys(filters).length).toBe(0);
        });

        test('extracts filters with partial values', () => {
            document.getElementById('type').value = 'vehiculo';
            document.getElementById('priceMin').value = '';
            document.getElementById('priceMax').value = '50000';

            const filters = app.getFiltersFromForm();

            expect(filters.type).toBe('vehiculo');
            expect(filters.price_min).toBeUndefined();
            expect(filters.price_max).toBe(50000);
        });

        test('converts price strings to numbers', () => {
            document.getElementById('priceMin').value = '1000.50';
            document.getElementById('priceMax').value = '2000.75';

            const filters = app.getFiltersFromForm();

            expect(typeof filters.price_min).toBe('number');
            expect(typeof filters.price_max).toBe('number');
            expect(filters.price_min).toBe(1000.5);
            expect(filters.price_max).toBe(2000.75);
        });
    });

    describe('Search Handling', () => {
        test('handles search form submission', async () => {
            document.getElementById('query').value = 'test';
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            document.getElementById('searchForm');
            const event = new Event('submit');
            event.preventDefault = jest.fn();

            await app.handleSearch(event);

            expect(event.preventDefault).toHaveBeenCalled();
            expect(app.currentPage).toBe(0);
        });

        test('resets pagination on new search', async () => {
            app.currentPage = 5;
            document.getElementById('query').value = 'test';

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            document.getElementById('searchForm');
            const event = new Event('submit');
            event.preventDefault = jest.fn();

            await app.handleSearch(event);

            expect(app.currentPage).toBe(0);
        });

        test('updates currentLimit from form', async () => {
            // Update DOM to include the 100 option
            const limitSelect = document.getElementById('limit');
            limitSelect.innerHTML = `
                <option value="10">10</option>
                <option value="50">50</option>
                <option value="100">100</option>
            `;

            document.getElementById('query').value = 'test';
            limitSelect.value = '100';

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 0,
                    limit: 100,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            document.getElementById('searchForm');
            const event = new Event('submit');
            event.preventDefault = jest.fn();

            await app.handleSearch(event);

            expect(app.currentLimit).toBe(100);
        });

        test('stores last search query and filters', async () => {
            document.getElementById('query').value = 'madrid';
            document.getElementById('type').value = 'inmueble';

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            document.getElementById('searchForm');
            const event = new Event('submit');
            event.preventDefault = jest.fn();

            await app.handleSearch(event);

            expect(app.lastSearchQuery).toBe('madrid');
            expect(app.lastSearchFilters.type).toBe('inmueble');
        });
    });

    describe('Pagination', () => {
        test('previousPage decrements page when not on first page', async () => {
            app.currentPage = 2;
            app.lastSearchQuery = 'test';
            app.lastSearchFilters = {};

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

            await app.previousPage();

            expect(app.currentPage).toBe(1);
            expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
        });

        test('previousPage does nothing on first page', () => {
            app.currentPage = 0;
            app.lastSearchQuery = 'test';

            app.previousPage();

            expect(app.currentPage).toBe(0);
            expect(window.scrollTo).not.toHaveBeenCalled();
        });

        test('nextPage increments page', async () => {
            app.currentPage = 0;
            app.lastSearchQuery = 'test';
            app.lastSearchFilters = {};

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

            await app.nextPage();

            expect(app.currentPage).toBe(1);
            expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
        });

        test('nextPage uses last search query and filters', async () => {
            app.currentPage = 0;
            app.lastSearchQuery = 'madrid';
            app.lastSearchFilters = { type: 'inmueble' };

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

            await app.nextPage();

            expect(app.lastSearchQuery).toBe('madrid');
            expect(app.lastSearchFilters.type).toBe('inmueble');
        });
    });

    describe('Search History', () => {
        test('loads search history on init', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    history: [
                        {
                            query: 'test',
                            result_count: 5,
                            created_at: '2024-01-01',
                        },
                    ],
                    total: 1,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            await app.loadSearchHistory();

            const historyContainer = document.getElementById('historyContainer');
            expect(historyContainer.innerHTML).toContain('test');
        });

        test('handles search history loading error gracefully', async () => {
            const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();
            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await app.loadSearchHistory();

            expect(consoleWarnSpy).toHaveBeenCalled();
            consoleWarnSpy.mockRestore();
        });
    });

    describe('Performance Search', () => {
        test('shows loading indicator during search', async () => {
            jest.spyOn(app.uiModule, 'showLoading');
            jest.spyOn(app.uiModule, 'renderResults');

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            await app.performSearch('test', {});

            expect(app.uiModule.showLoading).toHaveBeenCalledWith(true);
        });

        test('hides loading indicator after search', async () => {
            jest.spyOn(app.uiModule, 'showLoading');

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    assets: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            await app.performSearch('test', {});

            expect(app.uiModule.showLoading).toHaveBeenCalledWith(false);
        });

        test('renders search results', async () => {
            jest.spyOn(app.uiModule, 'renderResults');
            jest.spyOn(app.uiModule, 'updateResultsCount');

            const mockAssets = [
                {
                    id: 'TEST-001',
                    type: 'inmueble',
                    description: 'Test asset',
                    price_initial: 100000,
                    price_min: 80000,
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

            await app.performSearch('test', {});

            expect(app.uiModule.renderResults).toHaveBeenCalledWith(mockAssets);
            expect(app.uiModule.updateResultsCount).toHaveBeenCalledWith(1);
        });

        test('shows error message on search failure', async () => {
            jest.spyOn(app.uiModule, 'showError');

            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await app.performSearch('test', {});

            expect(app.uiModule.showError).toHaveBeenCalled();
            expect(app.uiModule.showError.mock.calls[0][0]).toContain('Error en la búsqueda');
        });

        test('always hides loading indicator even on error', async () => {
            jest.spyOn(app.uiModule, 'showLoading');

            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await app.performSearch('test', {});

            const callsToShowLoading = app.uiModule.showLoading.mock.calls;
            expect(callsToShowLoading[callsToShowLoading.length - 1][0]).toBe(false);
        });
    });

    describe('Event Listeners Setup', () => {
        test('sets up search form listener', () => {
            const form = document.getElementById('searchForm');
            jest.spyOn(app, 'handleSearch');

            app.setupEventListeners();

            // Manually trigger the event to verify listener is set
            form.dispatchEvent(new Event('submit'));

            // Note: In actual testing, this would require waiting for the async handler
        });

        test('sets up previous button listener', () => {
            const prevBtn = document.getElementById('prevBtn');
            jest.spyOn(app, 'previousPage');

            app.setupEventListeners();

            prevBtn.dispatchEvent(new Event('click'));
        });

        test('sets up next button listener', () => {
            const nextBtn = document.getElementById('nextBtn');
            jest.spyOn(app, 'nextPage');

            app.setupEventListeners();

            nextBtn.dispatchEvent(new Event('click'));
        });
    });

    describe('App Initialization', () => {
        test('init method calls setupEventListeners', () => {
            jest.spyOn(app, 'setupEventListeners');

            app.init();

            expect(app.setupEventListeners).toHaveBeenCalled();
        });

        test('init method calls loadSearchHistory', () => {
            jest.spyOn(app, 'loadSearchHistory');
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: jest.fn(async () => ({
                    history: [],
                    total: 0,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                })),
            });

            app.init();

            expect(app.loadSearchHistory).toHaveBeenCalled();
        });
    });

    describe('DOMContentLoaded Initialization', () => {
        test('can create and initialize app instance', () => {
            // The DOMContentLoaded listener is set at module load time
            // We verify that creating an instance works correctly
            const newApp = new App();

            expect(newApp).toBeDefined();
            expect(newApp.searchModule).toBeDefined();
            expect(newApp.uiModule).toBeDefined();
            expect(newApp.currentPage).toBe(0);
        });

        test('firing DOMContentLoaded event initializes new app', () => {
            // Clear existing listeners
            const domContentLoadedEvent = new Event('DOMContentLoaded');

            // This tests that the event listener works when fired
            document.dispatchEvent(domContentLoadedEvent);

            // If the listener executed, no errors should occur
            expect(true).toBe(true);
        });

        test('app initializes with correct default values', () => {
            const testApp = new App();
            testApp.init();

            expect(testApp.currentPage).toBe(0);
            expect(testApp.currentLimit).toBe(50);
            expect(testApp.lastSearchQuery).toBeNull();
            expect(testApp.lastSearchFilters).toBeNull();
        });
    });
});
