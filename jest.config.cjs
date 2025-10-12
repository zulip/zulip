module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  transform: {
    '^.+\\.tsx?$': 'ts-jest',
  },
  moduleNameMapper: {
    '\\.(hbs)$': '<rootDir>/web/tests/lib/handlebarsMock.cjs',
  },
  setupFiles: ['<rootDir>/web/tests/setupTests.ts'],
  testMatch: ['**/web/tests/**/*.test.ts?(x)'],
  globals: {
    'ts-jest': {
      tsconfig: 'tsconfig.test.json',
    },
  },
};
