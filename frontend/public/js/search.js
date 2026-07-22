export class SearchModule {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
    }

    async search(query = '', filters = {}, limit = 50, offset = 0) {
        try {
            const queryParams = this.buildQueryParams(query, filters, limit, offset);
            const url = `${this.apiBaseUrl}/search${queryParams}`;

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            return {
                assets: data.assets || [],
                total: data.total || 0,
                limit: data.limit || limit,
                offset: data.offset || offset,
                timestamp: data.timestamp,
            };
        } catch (error) {
            throw new Error(`Failed to search assets: ${error.message}`);
        }
    }

    async getAsset(assetId) {
        try {
            const url = `${this.apiBaseUrl}/assets/${encodeURIComponent(assetId)}`;

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
            });

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Asset not found');
                }
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            return data.asset;
        } catch (error) {
            throw new Error(`Failed to get asset: ${error.message}`);
        }
    }

    async getSearchHistory(limit = 50, offset = 0) {
        try {
            const queryParams = new URLSearchParams({
                limit: limit.toString(),
                offset: offset.toString(),
            }).toString();

            const url = `${this.apiBaseUrl}/search-history?${queryParams}`;

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            return {
                history: data.history || [],
                total: data.total || 0,
                limit: data.limit || limit,
                offset: data.offset || offset,
                timestamp: data.timestamp,
            };
        } catch (error) {
            throw new Error(`Failed to load search history: ${error.message}`);
        }
    }

    async getHealth() {
        try {
            const url = `${this.apiBaseUrl}/health`;

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            return data;
        } catch (error) {
            throw new Error(`Failed to check API health: ${error.message}`);
        }
    }

    buildQueryParams(query = '', filters = {}, limit = 50, offset = 0) {
        const params = new URLSearchParams();

        if (query && query.trim()) {
            params.append('q', query.trim());
        }

        if (filters.type) {
            params.append('type', filters.type);
        }

        if (filters.price_min !== undefined && filters.price_min !== null && filters.price_min !== '') {
            params.append('price_min', filters.price_min);
        }

        if (filters.price_max !== undefined && filters.price_max !== null && filters.price_max !== '') {
            params.append('price_max', filters.price_max);
        }

        if (filters.date_from) {
            params.append('date_from', filters.date_from);
        }

        if (filters.date_to) {
            params.append('date_to', filters.date_to);
        }

        params.append('limit', limit);
        params.append('offset', offset);

        return params.toString() ? `?${params.toString()}` : '';
    }
}
