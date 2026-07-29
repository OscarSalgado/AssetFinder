// Intl formatters are expensive to construct and were previously rebuilt on
// every cell (~150 per page of 50 results). Built once, reused for the page.
const PRICE_FORMATTER = new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

const DATE_FORMATTER = new Intl.DateTimeFormat('es-ES', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
});

// Static escape table: avoids creating a throwaway DOM element per call
// (escapeHtml runs ~6 times per card).
const HTML_ESCAPES = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
};

const HTML_ESCAPE_PATTERN = /[&<>"']/g;

export class UIModule {
    constructor() {
        this.resultsContainer = document.getElementById('resultsContainer');
        this.resultsCount = document.getElementById('resultsCount');
        this.loadingIndicator = document.getElementById('loadingIndicator');
        this.paginationControls = document.getElementById('paginationControls');
        this.historyContainer = document.getElementById('historyContainer');
    }

    renderResults(assets) {
        if (!this.resultsContainer) return;

        if (!assets || assets.length === 0) {
            this.resultsContainer.innerHTML = '<p class="empty-state">No se encontraron resultados</p>';
            return;
        }

        this.resultsContainer.innerHTML = assets.map((asset) => this.createAssetCard(asset)).join('');
    }

    createAssetCard(asset) {
        const assetType = this.getAssetTypeBadge(asset.type);
        const priceInitial = this.formatPrice(asset.price_initial);
        const priceMin = asset.price_min ? this.formatPrice(asset.price_min) : 'N/A';
        const location = asset.location || 'No especificado';

        return `
            <div class="asset-card" data-asset-id="${this.escapeHtml(asset.id)}">
                <div class="asset-card-header">
                    <div>
                        <div class="asset-id">${this.escapeHtml(asset.id)}</div>
                        <div class="asset-type ${this.escapeHtml(asset.type)}">${this.escapeHtml(asset.type)}</div>
                    </div>
                </div>
                <div class="asset-description">
                    ${this.escapeHtml(asset.description.substring(0, 200))}${asset.description.length > 200 ? '...' : ''}
                </div>
                <div class="asset-details">
                    <div class="asset-detail-item">
                        <div class="asset-detail-label">Precio Inicial</div>
                        <div class="asset-detail-value asset-price">${priceInitial}</div>
                    </div>
                    <div class="asset-detail-item">
                        <div class="asset-detail-label">Puja Mínima</div>
                        <div class="asset-detail-value asset-price">${priceMin}</div>
                    </div>
                    <div class="asset-detail-item">
                        <div class="asset-detail-label">Fecha de Subasta</div>
                        <div class="asset-detail-value">${this.formatDate(asset.date_subasta)}</div>
                    </div>
                    <div class="asset-detail-item">
                        <div class="asset-detail-label">Ubicación</div>
                        <div class="asset-detail-value">${this.escapeHtml(location)}</div>
                    </div>
                </div>
            </div>
        `;
    }

    getAssetTypeBadge(type) {
        const types = {
            inmueble: 'Inmueble',
            vehiculo: 'Vehículo',
            mueble: 'Mueble',
            otros: 'Otros',
        };
        return types[type] || type;
    }

    formatPrice(price) {
        if (!price || price === 0) return '€ 0,00';
        return `€ ${PRICE_FORMATTER.format(parseFloat(price))}`;
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        try {
            const date = new Date(dateString);
            if (isNaN(date.getTime())) {
                return dateString;
            }
            return DATE_FORMATTER.format(date);
        } catch {
            return dateString;
        }
    }

    updateResultsCount(total) {
        if (this.resultsCount) {
            const pluralWord = total === 1 ? 'resultado' : 'resultados';
            this.resultsCount.textContent = `${total} ${pluralWord}`;
        }
    }

    updatePaginationControls(total, limit, offset) {
        if (!this.paginationControls) return;

        const currentPage = Math.floor(offset / limit) + 1;
        const totalPages = Math.ceil(total / limit);
        const hasNextPage = offset + limit < total;

        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const pageInfo = document.getElementById('pageInfo');

        if (total === 0 || totalPages <= 1) {
            this.paginationControls.style.display = 'none';
            return;
        }

        this.paginationControls.style.display = 'flex';

        if (prevBtn) {
            prevBtn.disabled = offset === 0;
        }

        if (nextBtn) {
            nextBtn.disabled = !hasNextPage;
        }

        if (pageInfo) {
            pageInfo.textContent = `Página ${currentPage} de ${totalPages}`;
        }
    }

    renderSearchHistory(historyData) {
        if (!this.historyContainer || !historyData || !historyData.history || historyData.history.length === 0) {
            if (this.historyContainer) {
                this.historyContainer.innerHTML = '<p class="empty-state">No hay búsquedas registradas</p>';
            }
            return;
        }

        this.historyContainer.innerHTML = historyData.history
            .map((item) => this.createHistoryItem(item))
            .join('');
    }

    createHistoryItem(item) {
        const query = item.query || '(búsqueda vacía)';
        const resultCount = item.result_count || 0;
        const timestamp = this.formatDate(item.created_at) || 'Desconocida';

        return `
            <div class="history-item">
                <div class="history-item-query">Búsqueda: "${this.escapeHtml(query)}"</div>
                <div class="history-item-meta">
                    <span>${resultCount} ${resultCount === 1 ? 'resultado' : 'resultados'}</span>
                    <span>${timestamp}</span>
                </div>
            </div>
        `;
    }

    showLoading(isLoading) {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = isLoading ? 'inline' : 'none';
        }
    }

    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;

        const resultsSection = document.querySelector('.results-section');
        if (resultsSection) {
            resultsSection.insertBefore(errorDiv, resultsSection.firstChild);

            setTimeout(() => {
                errorDiv.remove();
            }, 5000);
        }
    }

    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.textContent = message;

        const resultsSection = document.querySelector('.results-section');
        if (resultsSection) {
            resultsSection.insertBefore(successDiv, resultsSection.firstChild);

            setTimeout(() => {
                successDiv.remove();
            }, 5000);
        }
    }

    escapeHtml(text) {
        if (!text) return '';
        return String(text).replace(HTML_ESCAPE_PATTERN, (char) => HTML_ESCAPES[char]);
    }
}
