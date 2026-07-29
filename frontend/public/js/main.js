import { SearchModule } from './search.js';
import { UIModule } from './ui.js';

export class App {
    constructor() {
        this.apiBaseUrl = this.getApiBaseUrl();
        this.searchModule = new SearchModule(this.apiBaseUrl);
        this.uiModule = new UIModule();
        this.currentPage = 0;
        this.currentLimit = 50;
        this.lastSearchQuery = null;
        this.lastSearchFilters = null;
        this.lastTotal = null;
        // Monotonic counter so a slow response cannot overwrite a newer one.
        this.searchGeneration = 0;
    }

    get currentOffset() {
        return this.currentPage * this.currentLimit;
    }

    getApiBaseUrl() {
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        const port = window.location.port ? `:${window.location.port}` : '';
        return `${protocol}//${hostname}${port}/api`;
    }

    init() {
        this.setupEventListeners();
        this.loadSearchHistory();
    }

    setupEventListeners() {
        const searchForm = document.getElementById('searchForm');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');

        if (searchForm) {
            searchForm.addEventListener('submit', (e) => this.handleSearch(e));
        }

        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.previousPage());
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.nextPage());
        }
    }

    async handleSearch(event) {
        event.preventDefault();

        const query = document.getElementById('query').value.trim();
        const filters = this.getFiltersFromForm();

        this.currentPage = 0;
        this.currentLimit = parseInt(document.getElementById('limit').value) || 50;
        this.lastSearchQuery = query;
        this.lastSearchFilters = filters;
        this.lastTotal = null;

        await this.performSearch(query, filters);
    }

    getFiltersFromForm() {
        const type = document.getElementById('type').value;
        const priceMin = document.getElementById('priceMin').value;
        const priceMax = document.getElementById('priceMax').value;
        const dateFrom = document.getElementById('dateFrom').value;
        const dateTo = document.getElementById('dateTo').value;

        const filters = {};

        if (type) filters.type = type;
        if (priceMin) filters.price_min = parseFloat(priceMin);
        if (priceMax) filters.price_max = parseFloat(priceMax);
        if (dateFrom) filters.date_from = dateFrom;
        if (dateTo) filters.date_to = dateTo;

        return filters;
    }

    async performSearch(query, filters) {
        const generation = ++this.searchGeneration;

        try {
            this.uiModule.showLoading(true);

            // currentOffset (page * limit), not the page index: the API paginates
            // by record offset.
            const offset = this.currentOffset;
            const results = await this.searchModule.search(query, filters, this.currentLimit, offset);

            // A newer search was started while this one was in flight.
            if (generation !== this.searchGeneration) return;

            this.lastTotal = results.total;
            this.uiModule.renderResults(results.assets);
            this.uiModule.updateResultsCount(results.total);
            this.uiModule.updatePaginationControls(results.total, this.currentLimit, offset);

        } catch (error) {
            // An aborted request was superseded on purpose, not a failure.
            if (error.name === 'AbortError') return;
            this.uiModule.showError(`Error en la búsqueda: ${error.message}`);
        } finally {
            if (generation === this.searchGeneration) {
                this.uiModule.showLoading(false);
            }
        }
    }

    previousPage() {
        if (this.currentPage > 0) {
            this.currentPage--;
            this.performSearch(this.lastSearchQuery, this.lastSearchFilters);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    nextPage() {
        // Do not walk past the last page once the total is known.
        if (this.lastTotal !== null && this.currentOffset + this.currentLimit >= this.lastTotal) {
            return;
        }

        this.currentPage++;
        this.performSearch(this.lastSearchQuery, this.lastSearchFilters);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    async loadSearchHistory() {
        try {
            const history = await this.searchModule.getSearchHistory();
            this.uiModule.renderSearchHistory(history);
        } catch (error) {
            // Silently fail if history is not available
            console.warn('Could not load search history:', error);
        }
    }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
});
