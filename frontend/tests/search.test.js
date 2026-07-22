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
            expect(result).toBe('?limit=50&offset=0');
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
                    timestamp: '2024-01-01T00:00:00Z',
                }),
            });

            const result = await searchModule.search('test');

            expect(result.assets).toEqual(mockAssets);
            expect(result.total).toBe(1);
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
    });
});
