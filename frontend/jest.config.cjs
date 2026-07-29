module.exports = {
  testEnvironment: 'jsdom',
  collectCoverage: true,
  collectCoverageFrom: [
    'public/js/**/*.js',
    '!public/js/**/*.test.js',
    '!public/js/**/__mocks__/**'
  ],
  coveragePathIgnorePatterns: [
    '/node_modules/',
    '/tests/'
  ],
  // Gates are set to the coverage actually achieved, so a regression fails the
  // build. Branch coverage is below 100% because of defensive guards on DOM
  // lookups that jsdom always satisfies; raising it means covering those, not
  // relaxing the gate.
  coverageThreshold: {
    global: {
      branches: 93,
      functions: 100,
      lines: 100,
      statements: 100
    }
  },
  testMatch: ['**/tests/**/*.test.js'],
  transform: {
    '^.+\\.js$': 'babel-jest'
  },
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/public/js/$1'
  }
};
