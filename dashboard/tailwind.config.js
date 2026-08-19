/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Identidade visual Alchemia -- extraída de alchemia-growth/branding/logos/ e da
        // convenção já validada em .claude/skills/realtime-dashboard/SKILL.md.
        navy: {
          950: '#060c1e',
          900: '#0a1730',
          800: '#101f42',
        },
        cyan: {
          accent: '#29d3f5',
        },
        status: {
          done: '#33d69f',
          progress: '#6fa8ff',
          start: '#ffb648',
          risk: '#ff6472',
          idle: '#4a5a80',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'Cascadia Code', 'Consolas', 'monospace'],
        sans: ['-apple-system', 'Segoe UI', 'Inter', 'sans-serif'],
      },
      backgroundImage: {
        'alchemia-gradient': 'linear-gradient(135deg, #060c1e 0%, #101f42 100%)',
      },
    },
  },
  plugins: [],
};
