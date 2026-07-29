import { SearchModule } from '../public/js/search.js';

describe('SearchModule', () => {
    let searchModule;

    beforeEach(() => {
        searchModule = new SearchModule('http://localhost:5000/api');
        global.fetch.mockClear();
    });

    describe('buildQueryParams', () => {
        test('builds empty query params with no arguments', () => {
            const result = searchModule.buildQueryParams('', {});
            expect(result).toContain('limit=50');
            expect(result).toContain('offset=0');
            expect(result).toContain('sort_by=date_subasta');
            expect(result).toContain('sort_order=DESC');
        });

        test('includes query parameter when provided', () => {
            const result = searchModule.buildQueryParams('madrid', {});
            expect(result).toContain('q=madrid');
        });

        test('includes type filter when provided', () => {
            const result = searchModule.buildQueryParams('', { type: 'inmueble' });
            expect(result).toContain('type=inmueble');
        });

        test('includes price min when provided', () => {
            const result = searchModule.buildQueryParams('', { price_min: 10000 });
            expect(result).toContain('price_min=10000');
        });

        test('includes price max when provided', () => {
            const result = searchModule.buildQueryParams('', { price_max: 50000 });
            expect(result).toContain('price_max=50000');
        });

        test('includes date filters when provided', () => {
            const result = searchModule.buildQueryParams('', {
                date_from: '2024-01-01',
                date_to: '2024-12-31',
            });
            expect(result).toContain('date_from=2024-01-01');
            expect(result).toContain('date_to=2024-12-31');
        });

        test('includes limit and offset', () => {
            const result = searchModule.buildQueryParams('', {}, 100, 50);
            expect(result).toContain('limit=100');
            expect(result).toContain('offset=50');
        });

        test('ignores empty price values', () => {
            const result = searchModule.buildQueryParams('', { price_min: '', price_max: null });
            expect(result).not.toContain('price_min=');
            expect(result).not.toContain('price_max=');
        });

        test('includes sort_by parameter', () => {
            const result = searchModule.buildQueryParams('', {}, 50, 0, 'price_initial', 'ASC');
            expect(result).toContain('sort_by=price_initial');
            expect(result).toContain('sort_order=ASC');
        });

        test('defaults to date_subasta sort', () => {
            const result = searchModule.buildQueryParams('', {});
            expect(result).toContain('sort_by=date_subasta');
            expect(result).toContain('sort_order=DESC');
        });
    });

    describe('search', () => {
        test('makes correct API call to search endpoint', async () => {
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

            await searchModule.search('test', {}, 50, 0);

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/search'),
                expect.objectContaining({
                    method: 'GET',
                    headers: expect.objectContaining({
                        'Content-Type': 'application/json',
                    }),
                })
            );
        });

        test('returns search results correctly', async () => {
            const mockAssets = [
                { id: '001', type: 'inmueble', description: 'Test', price_initial: 100000 },
            ];

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    assets: mockAssets,
                    total: 1,
                    limit: 50,
                    offset: 0,
                    sort_by: 'date_subasta',
                    sort_order: 'DESC',
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const result = await searchModule.search('test');

            expect(result.assets).toEqual(mockAssets);
            expect(result.total).toBe(1);
            expect(result.sortBy).toBe('date_subasta');
            expect(result.sortOrder).toBe('DESC');
        });

        test('throws error on failed API response', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
            });

            await expect(searchModule.search()).rejects.toThrow('API error');
        });

        test('throws error on network failure', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await expect(searchModule.search()).rejects.toThrow('Failed to search assets');
        });
    });

    describe('getAsset', () => {
        test('makes correct API call to get asset endpoint', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    asset: { id: '001', type: 'inmueble', description: 'Test' },
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            await searchModule.getAsset('001');

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/assets/001'),
                expect.any(Object)
            );
        });

        test('throws error when asset not found', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 404,
                statusText: 'Not Found',
            });

            await expect(searchModule.getAsset('nonexistent')).rejects.toThrow('Asset not found');
        });

        test('throws error on other API errors', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
            });

            await expect(searchModule.getAsset('001')).rejects.toThrow('API error');
        });

        test('encodes asset ID properly', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ asset: {} }),
            });

            await searchModule.getAsset('SSSS-2024-001/special');

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining(encodeURIComponent('SSSS-2024-001/special')),
                expect.any(Object)
            );
        });

        test('throws error on fetch failure', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await expect(searchModule.getAsset('001')).rejects.toThrow('Failed to get asset');
        });
    });

    describe('getSearchHistory', () => {
        test('makes correct API call to search history endpoint', async () => {
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

            await searchModule.getSearchHistory(50, 0);

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/search-history'),
                expect.any(Object)
            );
        });

        test('returns search history correctly', async () => {
            const mockHistory = [
                { query: 'test', result_count: 10, created_at: '2024-01-01T00:00:00Z' },
            ];

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    history: mockHistory,
                    total: 1,
                    limit: 50,
                    offset: 0,
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const result = await searchModule.getSearchHistory();

            expect(result.history).toEqual(mockHistory);
            expect(result.total).toBe(1);
        });

        test('throws error on failed API response', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
            });

            await expect(searchModule.getSearchHistory()).rejects.toThrow('API error');
        });

        test('throws error on network failure', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await expect(searchModule.getSearchHistory()).rejects.toThrow('Failed to load search history');
        });
    });

    describe('getHealth', () => {
        test('makes correct API call to health endpoint', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    status: 'ok',
                    timestamp: '2024-01-01T00:00:00Z',
                    scraper: { healthy: true },
                    database: { connected: true },
                }),
            });

            await searchModule.getHealth();

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/health'),
                expect.any(Object)
            );
        });

        test('returns health status correctly', async () => {
            const mockHealth = {
                status: 'ok',
                timestamp: '2024-01-01T00:00:00Z',
                scraper: { healthy: true },
                database: { connected: true },
            };

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => mockHealth,
            });

            const result = await searchModule.getHealth();

            expect(result.status).toBe('ok');
            expect(result.scraper.healthy).toBe(true);
            expect(result.database.connected).toBe(true);
        });

        test('throws error on failed API response', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error',
            });

            await expect(searchModule.getHealth()).rejects.toThrow('API error');
        });

        test('throws error on network failure', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await expect(searchModule.getHealth()).rejects.toThrow('Failed to check API health');
        });
    });

    describe('Edge Cases and Branch Coverage', () => {
        test('buildQueryParams ignores undefined price_min', () => {
            const result = searchModule.buildQueryParams('', { price_min: undefined });
            expect(result).not.toContain('price_min=undefined');
        });

        test('buildQueryParams includes price_min = 0', () => {
            const result = searchModule.buildQueryParams('', { price_min: 0 });
            expect(result).toContain('price_min=0');
        });

        test('buildQueryParams handles whitespace-only query', () => {
            const result = searchModule.buildQueryParams('   ', {});
            expect(result).not.toContain('q=');
        });

        test('buildQueryParams includes all filters together', () => {
            const result = searchModule.buildQueryParams('madrid', {
                type: 'inmueble',
                price_min: 50000,
                price_max: 200000,
                date_from: '2024-01-01',
                date_to: '2024-12-31',
            }, 100, 25);

            expect(result).toContain('q=madrid');
            expect(result).toContain('type=inmueble');
            expect(result).toContain('price_min=50000');
            expect(result).toContain('price_max=200000');
            expect(result).toContain('date_from=2024-01-01');
            expect(result).toContain('date_to=2024-12-31');
            expect(result).toContain('limit=100');
            expect(result).toContain('offset=25');
        });

        test('search with empty assets array returns empty results', async () => {
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

            const result = await searchModule.search('nonexistent');

            expect(result.assets).toEqual([]);
            expect(result.total).toBe(0);
        });

        test('getAsset returns asset from response', async () => {
            const mockAsset = { id: '001', type: 'inmueble', description: 'Test asset' };

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ asset: mockAsset }),
            });

            const result = await searchModule.getAsset('001');

            expect(result).toEqual(mockAsset);
        });

        test('buildQueryParams maintains correct order of parameters', () => {
            const result = searchModule.buildQueryParams('test', { type: 'inmueble' }, 50, 0);

            expect(result).toContain('q=');
            expect(result).toContain('type=');
            expect(result).toContain('limit=');
            expect(result).toContain('offset=');
        });

        test('getSearchHistory uses default pagination values', async () => {
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

            const result = await searchModule.getSearchHistory();

            expect(result.limit).toBe(50);
            expect(result.offset).toBe(0);
        });

        test('search defaults undefined response fields', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    assets: [{ id: '001' }],
                    total: 1,
                }),
            });

            const result = await searchModule.search('test');

            expect(result.sortBy).toBeDefined();
            expect(result.sortOrder).toBeDefined();
            expect(result.timestamp).toBeUndefined();
        });
    });
});

describe('SearchModule request cancellation', () => {
    let searchModule;

    beforeEach(() => {
        searchModule = new SearchModule('http://localhost:5000/api');
        global.fetch = jest.fn();
    });

    test('search registers an in-flight controller', async () => {
        let capturedSignal = null;
        global.fetch.mockImplementation((url, options) => {
            capturedSignal = options.signal;
            return Promise.resolve({
                ok: true,
                json: async () => ({ assets: [], total: 0 }),
            });
        });

        await searchModule.search('piso');

        expect(capturedSignal).toBeInstanceOf(AbortSignal);
        expect(capturedSignal.aborted).toBe(false);
    });

    test('search clears the in-flight controller when it settles', async () => {
        global.fetch.mockResolvedValue({
            ok: true,
            json: async () => ({ assets: [], total: 0 }),
        });

        await searchModule.search('piso');

        expect(searchModule.inFlightSearch).toBeNull();
    });

    test('a new search aborts the previous in-flight request', async () => {
        const signals = [];
        global.fetch.mockImplementation((url, options) => {
            signals.push(options.signal);
            // Never settles: keeps the request in flight.
            return new Promise(() => {});
        });

        searchModule.search('primera');
        searchModule.search('segunda');

        expect(signals).toHaveLength(2);
        expect(signals[0].aborted).toBe(true);
        expect(signals[1].aborted).toBe(false);
    });

    test('abortInFlightSearch is a no-op when nothing is in flight', () => {
        expect(searchModule.inFlightSearch).toBeNull();
        expect(() => searchModule.abortInFlightSearch()).not.toThrow();
        expect(searchModule.inFlightSearch).toBeNull();
    });

    test('AbortError is rethrown unwrapped so callers can detect it', async () => {
        const abortError = new Error('The operation was aborted');
        abortError.name = 'AbortError';
        global.fetch.mockRejectedValue(abortError);

        await expect(searchModule.search('piso')).rejects.toMatchObject({
            name: 'AbortError',
        });
    });

    test('non-abort errors are still wrapped with context', async () => {
        global.fetch.mockRejectedValue(new Error('Network down'));

        await expect(searchModule.search('piso')).rejects.toThrow(
            'Failed to search assets: Network down'
        );
    });
});
