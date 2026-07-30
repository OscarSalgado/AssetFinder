import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const publicDir = path.join(__dirname, 'public');
const port = process.env.PORT || 3000;

const mimeTypes = {
    '.html': 'text/html',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
};

const server = http.createServer((req, res) => {
    // Parse URL
    const filePath = path.join(publicDir, req.url === '/' ? 'index.html' : req.url);

    // Security: prevent directory traversal
    if (!filePath.startsWith(publicDir)) {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
        return;
    }

    // Try to serve the file
    fs.readFile(filePath, (err, data) => {
        if (err) {
            // If file not found and it's not index.html, try index.html for SPA routing
            if (err.code === 'ENOENT' && req.url !== '/' && !req.url.includes('.')) {
                fs.readFile(path.join(publicDir, 'index.html'), (err, data) => {
                    if (err) {
                        res.writeHead(404, { 'Content-Type': 'text/plain' });
                        res.end('Not Found');
                        return;
                    }
                    res.writeHead(200, { 'Content-Type': 'text/html' });
                    res.end(data);
                });
                return;
            }

            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end('Not Found');
            return;
        }

        // Determine content type
        const ext = path.extname(filePath);
        const contentType = mimeTypes[ext] || 'application/octet-stream';

        // Add cache control headers
        const cacheControl = ext === '.html' ? 'no-cache, no-store, must-revalidate' : 'max-age=31536000';

        res.writeHead(200, {
            'Content-Type': contentType,
            'Cache-Control': cacheControl,
        });
        res.end(data);
    });
});

server.listen(port, () => {
    console.log(`Frontend server running at http://localhost:${port}`);
    console.log(`API proxy will route to backend on http://localhost:5000`);
});
