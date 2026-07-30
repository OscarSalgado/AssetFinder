import globals from 'globals';

export default [
    {
        // Browser modules: the app itself.
        files: ['public/js/**/*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: globals.browser,
        },
        rules: {
            // Catch the class of defect this project actually hit: a value
            // computed and then discarded (getAssetTypeBadge), and undeclared
            // identifiers.
            'no-unused-vars': ['error', { args: 'after-used' }],
            'no-undef': 'error',
            'no-implicit-globals': 'error',
            eqeqeq: ['error', 'always'],
            'no-var': 'error',
            'prefer-const': 'error',
            'no-console': ['warn', { allow: ['warn', 'error'] }],
            'no-return-await': 'error',
        },
    },
    {
        // Jest specs: jsdom plus the Jest globals.
        files: ['tests/**/*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: { ...globals.browser, ...globals.jest, ...globals.node },
        },
        rules: {
            'no-unused-vars': ['error', { args: 'none' }],
            'no-undef': 'error',
            eqeqeq: ['error', 'always'],
            'no-var': 'error',
            'prefer-const': 'error',
        },
    },
    {
        // Node scripts: the static file server and the benchmark.
        files: ['server.js', 'bench.mjs'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: globals.node,
        },
        rules: {
            'no-unused-vars': 'error',
            'no-undef': 'error',
            'no-var': 'error',
            'prefer-const': 'error',
        },
    },
];
