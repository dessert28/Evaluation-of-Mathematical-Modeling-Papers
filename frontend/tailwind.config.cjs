module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#080f1d',
        panel: '#111d30',
        line: '#1e2e46',
        muted: '#91a2bb',
      },
    },
  },
  plugins: [require('daisyui')],
  daisyui: {
    themes: [{
      nightwork: {
        primary: '#3b82f6', 'primary-content': '#f8fafc',
        secondary: '#64748b', 'secondary-content': '#f8fafc',
        accent: '#22d3ee', 'accent-content': '#082f49',
        neutral: '#17243a', 'neutral-content': '#e5edf9',
        'base-100': '#0b1424', 'base-200': '#111d30', 'base-300': '#1c2b42', 'base-content': '#e5edf9',
        info: '#38bdf8', success: '#34d399', warning: '#fbbf24', error: '#fb7185',
      },
    }],
  },
}
