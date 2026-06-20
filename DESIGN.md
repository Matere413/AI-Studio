# I-Studio Frontend — Design System (Tailwind)

> Basado en el design system de `ds-i-studio-plataforma-de-marketing-design-system`
> Versión para Tailwind CSS v3+

---

## 1. Tono y Atmósfera Visual

**Serio, minimalista, técnico.** La interfaz debe comunicar precisión, control y sofisticación profesional. Debe sentirse como una herramienta de grado industrial (Figma, DaVinci Resolve, Nuke). El contenido (imágenes, flujos) es el protagonista; la interfaz "desaparece" para dejar brillar el trabajo del usuario.

- Tono: serio y minimalista, que llame la atención de gente apasionada por el diseño
- Público objetivo: diseñadores, agencias y equipos de marketing

---

## 2. Color

El sistema usa **dark mode de alto contraste por defecto**, ideal para evaluación de imágenes y edición visual.

### Superficies

| Token               | Hex       | Uso                                         |
| ------------------- | --------- | ------------------------------------------- |
| `bg-base`           | `#1c1917` | Fondo principal de la aplicación            |
| `bg-surface`        | `#292524` | Paneles laterales, tarjetas, contenedores   |
| `bg-surface-hover`  | `#44403c` | Hover de elementos en paneles               |
| `border-default`    | `#2e2820` | Divisores de 1px, bordes de componentes     |

### Tipografía

| Token           | Hex       | Uso                                          |
| --------------- | --------- | -------------------------------------------- |
| `text-primary`  | `#F5F5F5` | Texto principal, títulos, valores de input   |
| `text-muted`    | `#8F8F8F` | Texto secundario, descripciones, placeholders|

### Acentos y Estados

| Token           | Hex       | Uso                                          |
| --------------- | --------- | -------------------------------------------- |
| `accent`        | `#d97706` | Naranja ámbar. Botones primarios, activos    |
| `highlight`     | `#eab208` | Amarillo dorado. Focus rings, activos        |
| `error`         | `#F28B82` | Rojo Material. Acciones destructivas         |
| `success`       | `#81C995` | Verde Material. Flujos completados           |

### Mapeo a Tailwind

```js
// tailwind.config.js
colors: {
  base:    '#1c1917',
  surface: {
    DEFAULT: '#292524',
    hover:   '#44403c',
  },
  border:  '#2e2820',
  primary: '#F5F5F5',
  muted:   '#8F8F8F',
  accent:  '#d97706',
  highlight: '#eab208',
  error:   '#F28B82',
  success: '#81C995',
}
```

---

## 3. Tipografía

Tipografía geométrica y limpia que evoca el diseño suizo y la precisión técnica.

| Uso        | Font Stack                                                     | Pesos         |
| ---------- | -------------------------------------------------------------- | ------------- |
| Headings   | `system-ui, -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif` | 400, 500 |
| Body / UI  | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`     | 400           |
| Mono       | `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace` | 400       |

- **Letter-spacing**: `0.02em` para labels y botones; `0.06em` para texto en ALL CAPS
- **Font size base**: 14px (body)
- **H1**: 24px, **H2**: 20px, **H3**: 16px
- No usar bold 700+. Mantener elegancia con regular y medium.

### Mapeo a Tailwind

```js
fontFamily: {
  display: ['system-ui', '-apple-system', 'Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
  body:    ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
  mono:    ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
}
```

---

## 4. Espaciado y Radio

Escala base de **4px** para precisión en interfaces de herramientas.

| Token     | px   | Tailwind | Uso                                       |
| --------- | ---- | -------- | ----------------------------------------- |
| micro     | 4px  | `1`      | Gap entre icono y texto                   |
| tight     | 8px  | `2`      | Padding interno de inputs, list items     |
| base      | 16px | `4`      | Padding de paneles, gap entre secciones   |
| loose     | 24px | `6`      | Márgenes de vista principal               |
| spacious  | 32px | `8`      | Separación entre layouts mayores          |
| layout    | 48px | `12`     | Separación de secciones grandes           |

### Border Radius

| Token  | px    | Tailwind | Uso                                       |
| ------ | ----- | -------- | ----------------------------------------- |
| none   | 0px   | `none`   | Paneles estructurales                     |
| sm     | 8px   | `lg`     | Inputs, selects, items                    |
| md     | 12px  | `xl`     | Paneles principales                       |
| lg     | 100px | `full`   | Botones pill-shaped                       |

---

## 5. Layout y Composición

- **Estructura de herramienta conversacional**: Sidebar izquierdo con el chat del Agente. Área principal a la derecha como Studio/Workspace (canvas expandido, sin bordes de tarjeta).
- **Assets laterales**: Menú colapsable a la derecha para archivos subidos (no cajas flotantes).
- **Densidad de información**: Moderada a alta. Controles técnicos abstractos en inputs rápidos (Speed, Format).
- **Bordes sobre sombras**: Separar capas con `border` de 1px (`#2e2820`), NO con `box-shadow`.
- **Sidebar**: 300-320px de ancho.
- **Topbar**: 48px de alto.

---

## 6. Componentes

### Botones

| Variante   | Estilo                                                                 |
| ---------- | ---------------------------------------------------------------------- |
| Primary    | `bg-accent text-base`, pill shape (`rounded-full`), hover `bg-amber-500` |
| Secondary  | `bg-transparent text-primary border border-border`, hover `bg-surface-hover` |
| Ghost      | `bg-transparent text-primary opacity-70`, hover `opacity-100 bg-surface-hover` |

- **Focus visible**: Ring de 2px `border-highlight` / `#eab208`
- **Transición**: `150ms cubic-bezier(0.4, 0, 0.2, 1)`
- **Altura estándar**: 36px. Padding horizontal: 20px.

### Inputs y Selects

- Fondo `bg-surface`, borde `border-border`, sin borde visible en reposo
- Focus: borde `highlight` / `#eab208`
- Placeholder: `text-muted`
- Border-radius: 8px

### Chat Bubbles

- Usuario (derecha): fondo `bg-base`, borde `border-border`, border-radius `16px 16px 0 16px`
- Agente (izquierda): transparente, sin borde. Puede alojar tarjetas de contenido

### Gallery Items (Assets)

- Filas compactas en sidebar
- Hover: `bg-surface` con transición suave
- Icono (32×32) + filename + fecha

---

## 7. Movimiento e Interacción

- **Transitions**: Rápidas y secas. `150ms cubic-bezier(0.4, 0, 0.2, 1)` (Google standard easing).
- **No usar springs ni animaciones rebotantes**.
- **Loading**: Barras de progreso lineales finas (1-2px) en la parte superior del canvas. Nada de spinners ruidosos.
- **Scan line**: Para generar estado de "generando..." con línea de scan móvil.

---

## 8. Voz y Brand

- **Voz**: Técnica, directa, profesional y concisa.
- **Terminología**: "Workflow", "Orchestrator", "Prompt", "ControlNet", "Relighting".
- NO usar lenguaje excesivamente amigable ("¡Felicidades, tu imagen está lista!")
- Preferir: "Generación completada: 12.4s"
- Los textos de interfaz (labels, botones, errores) van en **inglés** por defecto.

---

## 9. Accesibilidad

- `aria-label` en todos los icon buttons
- `:focus-visible` rings custom con `border-highlight`
- HTML semántico: `<header>`, `<aside>`, `<main>`, `<nav>`
- `letter-spacing` estricto: `0.02em` UI labels, `0.06em` ALL CAPS
- Contraste suficiente sobre fondos oscuros

---

## 10. Anti-patrones

- ❌ **No usar gradients** ni fondos degradados vibrantes. Sólido o texturas de ruido sutil.
- ❌ **No usar sombras** pesadas o difusas para profundidad. Preferir bordes de 1px.
- ❌ **No usar tipografías redondeadas** (Quicksand, Nunito, Comic Sans).
- ❌ **No usar emojis** como iconos de interfaz. Usar iconografía SVG geométrica de línea fina (1-1.5px stroke).
- ❌ **No hacer interfaces "cozy"** con fondos cálidos. Mantener paleta neutra y fría/técnica.

---

## 11. Tailwind Config — Resumen Completo

```js
// tailwind.config.js
module.exports = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base:    '#1c1917',
        surface: {
          DEFAULT: '#292524',
          hover:   '#44403c',
        },
        border:  '#2e2820',
        primary: '#F5F5F5',
        muted:   '#8F8F8F',
        accent:  '#d97706',
        highlight: '#eab208',
        error:   '#F28B82',
        success: '#81C995',
      },
      fontFamily: {
        display: ['system-ui', '-apple-system', 'Helvetica Neue', 'Helvetica', 'Arial', 'sans-serif'],
        body:    ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono:    ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xl': ['24px', { lineHeight: '1.2' }],
        xl:    ['20px', { lineHeight: '1.2' }],
        lg:    ['16px', { lineHeight: '1.2' }],
        base:  ['14px', { lineHeight: '1.5' }],
        sm:    ['13px', { lineHeight: '1.5' }],
        xs:    ['11px', { lineHeight: '1.4' }],
      },
      spacing: {
        18: '4.5rem', // 72px — layout gaps
      },
      borderRadius: {
        sm:    '8px',
        md:    '12px',
      },
      transitionTimingFunction: {
        'studio': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      transitionDuration: {
        'studio': '150ms',
      },
      letterSpacing: {
        'ui':     '0.02em',
        'caps':   '0.06em',
      },
    },
  },
};
```

---

> **Fuente**: `ds-i-studio-plataforma-de-marketing-design-system/DESIGN.md`
