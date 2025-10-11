import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#2563eb',
        accent: '#f97316'
      }
    }
  },
  plugins: []
};

export default config;
