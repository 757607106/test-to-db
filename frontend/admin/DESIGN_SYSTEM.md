# RWX Data Design System (Glassmorphism Edition)

## 1. Design Philosophy
Our design language is built on **Apple-style Glassmorphism**, focusing on:
- **Translucency & Depth**: Using `backdrop-filter` and semi-transparent layers to create hierarchy.
- **Vibrant Neutrality**: A neutral slate background enhanced with subtle, vibrant gradients.
- **Content-First**: High contrast text and minimal borders to let data shine.
- **Fluid Interactions**: Smooth transitions and micro-interactions for a premium feel.

## 2. Color Palette

### Primary Colors
- **Primary**: `#6366f1` (Indigo 500) - Action buttons, active states, links.
- **Primary Hover**: `#4f46e5` (Indigo 600)
- **Secondary**: `#818cf8` (Indigo 400) - Accents, secondary highlights.
- **Accent**: `#2dd4bf` (Teal 400) - Success states, positive trends.

### Neutral Colors (Light Mode)
- **Text Main**: `#0f172a` (Slate 900)
- **Text Secondary**: `#475569` (Slate 600)
- **Text Tertiary**: `#94a3b8` (Slate 400)
- **Background Page**: `#f8fafc` (Slate 50) + Gradient Mesh
- **Background Card**: `#ffffff` (White)

### Glass Effects
| Token | Value (Light) | Value (Dark) | Description |
|-------|---------------|--------------|-------------|
| `--glass-bg` | `rgba(255, 255, 255, 0.75)` | `rgba(30, 30, 30, 0.65)` | Main container background |
| `--glass-bg-hover` | `rgba(255, 255, 255, 0.85)` | `rgba(45, 45, 45, 0.75)` | Hover state |
| `--glass-border-solid` | `rgba(255, 255, 255, 0.4)` | `rgba(255, 255, 255, 0.1)` | Subtle hairline borders |
| `--glass-blur` | `24px` | `24px` | Background blur amount |

## 3. Typography
**Font Stack**: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", sans-serif`

- **Headings**: Weights 600/700. Tight letter spacing (`-0.5px` for large titles).
- **Body**: Weight 400. Line height 1.5.
- **Monospace**: `'Roboto Mono', monospace` for SQL/Code.

## 4. Spacing & Layout
- **Grid Base**: 4px
- **Layout Gap**: 20px
- **Sidebar Width**: 260px
- **Header Height**: 60px

## 5. Component Specifications

### Cards & Panels
- **Background**: Glass Effect (`--glass-bg`)
- **Border**: 1px solid `--glass-border-solid`
- **Radius**: `16px` (`--border-radius-lg`)
- **Shadow**: `0 4px 24px rgba(0, 0, 0, 0.06)`

### Buttons
- **Primary**: Solid Indigo background, White text, no shadow (flat style) or subtle shadow.
- **Default/Ghost**: Glass background, Bordered.
- **Height**: 36px (Small: 28px, Large: 44px)
- **Radius**: 8px

### Inputs & Forms
- **Background**: `rgba(255, 255, 255, 0.5)` (Light) / `rgba(0, 0, 0, 0.2)` (Dark)
- **Border**: Transparent (until focus)
- **Focus**: Indigo border + Ring shadow

### Modals
- **Backdrop**: Blur `4px`, Background `rgba(0,0,0,0.2)`
- **Content**: Glass background, Shadow `0 20px 40px rgba(0,0,0,0.2)`
- **Animation**: Zoom in / Fade in

## 6. Interaction Guidelines
- **Hover**: Subtle lift (`translateY(-1px)`) + Background lighten.
- **Click**: Scale down (`scale(0.98)`).
- **Transitions**: `all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)` (Apple-like spring).
