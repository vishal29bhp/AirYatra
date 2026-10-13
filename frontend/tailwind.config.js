/** @type {import('tailwindcss').Config} */
// AirYatra theme (Vaayu Prive look, master prompt C.4); contrast ratios in docs/design/THEME.md.
// The app uses slate-* for every surface, border and secondary text, so remapping slate onto the
// aubergine scale themes all screens through tokens instead of per-component edits.
const aubergine = {
  50: '#F8F6FA',
  100: '#F2EEF6',
  200: '#E2DCE9',
  300: '#D0C9DA',
  400: '#A69DB3',
  500: '#8B819C',
  600: '#5A5068',
  700: '#3A3046',
  800: '#221A2D',
  900: '#17111F',
  950: '#0F0B15',
};

module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  // Some admin screens build colour classes at runtime (`bg-${config.color}-500/20`), which Tailwind cannot see.
  safelist: [
    { pattern: /^(bg|text|border)-(orange|amber|yellow|red|green|emerald|teal|cyan|blue|indigo|purple|pink|slate)-(400|500)(\/(10|20|30))?$/ },
  ],
  theme: {
  	extend: {
  		fontFamily: {
  			sans: ['"IBM Plex Sans"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
  			heading: ['"Barlow Condensed"', '"IBM Plex Sans"', 'sans-serif'],
  			mono: ['"JetBrains Mono"', 'Menlo', 'Monaco', 'Consolas', 'monospace']
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		colors: {
  			slate: aubergine,
  			lime: {
  				DEFAULT: '#C8F23C',
  				foreground: '#000000'
  			},
  			amber: {
  				DEFAULT: '#FFB000'
  			},
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
};