import { SearchModule } from './search.js';
import { UIModule } from './ui.js';

class App {
    constructor() {
        this.apiBaseUrl = this.getApiBaseUrl();
        this.searchModule = new SearchModule(this.apiBaseUrl);
        this.uiModule = new UIModule();
        this.currentPage = 0;
        this.currentLimit = 50;
        this.lastSearchQuery = null;
        this.lastSearchFilters = null;
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
        try {
            this.uiModule.showLoading(true);

            const results = await this.searchModule.search(query, filters, this.currentLimit, this.currentPage);

            this.uiModule.renderResults(results.assets);
            this.uiModule.updateResultsCount(results.total);
            this.uiModule.updatePaginationControls(results.total, this.currentLimit, this.currentPage);

        } catch (error) {
            this.uiModule.showError(`Error en la búsqueda: ${error.message}`);
        } finally {
            this.uiModule.showLoading(false);
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
