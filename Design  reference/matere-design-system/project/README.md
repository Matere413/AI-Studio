# Matere — Design System

> Interfaces con alma retro. Pixel craft, tierra cálida.

Matere es la marca y sistema de diseño personal de un diseñador de interfaces. Mezcla la calidez del papel envejecido con la precisión del píxel y la claridad de la tipografía moderna. Inspirado visualmente en la era del pixel art moderno (Celeste, Stardew Valley), con una paleta de atardecer quemado sobre tierra profunda.

Este no es un producto grande — es una firma. Un sistema que se usa para marcar diseños, prototipos, el portfolio personal y cualquier pieza de comunicación.

## Fuentes de origen
Este sistema fue creado desde cero por conversación con el usuario. No hay Figma ni codebase externo adjunto. Todas las decisiones vienen de:
- Preferencias del usuario: tierra + óxido, atardecer quemado, píxel balanceado, modern pixel art
- Efectos solicitados: scanlines sutiles, cursor parpadeante, drop shadows duras, grain cálido
- Lenguaje: bilingüe (español + inglés)
- Producto único: portfolio / sitio personal

---

## Index

### Raíz
- [`README.md`](./README.md) — este documento
- [`SKILL.md`](./SKILL.md) — skill reutilizable para Claude Code / Claude
- [`colors_and_type.css`](./colors_and_type.css) — tokens de color, tipografía, espaciado, sombras

### Carpetas
- [`fonts/`](./fonts/) — archivos .woff2 de Silkscreen, Pixelify Sans, VT323, Newsreader, Geist
- [`assets/`](./assets/) — logos, wordmark, set de iconos pixel
- [`preview/`](./preview/) — 19 cards de preview (se muestran en la pestaña Design System)
- [`ui_kits/portfolio/`](./ui_kits/portfolio/) — UI kit del portfolio personal (React + JSX)

---

## Content fundamentals

### Tono
Matere habla **cálido, conciso, artesanal**. Tono de alguien que hace cosas con cuidado y no grita.

- **Primera persona**, cercana. "Construyo productos cálidos." no "We build warm products."
- **Bilingüe**, mezcla natural. El español lleva el peso emocional ("interfaces con alma retro", "hecho un píxel a la vez"). El inglés lleva el peso funcional ("Work", "About", "Send").
- **Frases cortas**. Punto. Pausa. Otra frase.
- **Sin jerga corporativa**. Nada de "solutions", "leverage", "empowering".
- **Detalles específicos** en lugar de adjetivos vagos. "Escuchando vinilos" > "Con gustos variados".

### Casing
- **UI chrome** (botones, labels, eyebrows, tags, nav): `MAYÚSCULAS` con tracking 0.08–0.12em
- **Titulares**: `Sentence case` — "Interfaces con alma retro."
- **Body**: natural, sentence case
- **Código**: `lowercase-with-dashes`

### Emoji
**No se usan emoji.** Como reemplazo:
- Estado: `●` (pip coloreado) o badges con texto ("LIVE", "NEW")
- Decoración: sprites pixel pequeños, caracteres tipo `★ ✓ ← →` o iconos del set propio

### Vibra / voz
- "Un píxel a la vez."
- "Construido con cuidado."
- "Hecho a mano, no a escala."
- "Warm, not tech."

Frases a **evitar**: "revolutionary", "cutting-edge", "next-gen", "seamless", cualquier cosa que suene a pitch deck.

### Ejemplos reales
| Contexto | Copy |
|---|---|
| Eyebrow hero | `DISEÑO DE INTERFACES · 2026` |
| H1 | `Interfaces con alma retro.` |
| Sub | `Construyo productos digitales cálidos. Un píxel a la vez, con cuidado por el detalle y la tipografía.` |
| CTA primario | `Ver trabajo` / `See work` |
| Status pill | `Disponible desde Abr · 2026` |
| Footer | `Hecho un píxel a la vez` / `Made one pixel at a time` |
| Toast | `✓ Guardado` |
| Error | `Error` (corto, sin drama) |

---

## Visual foundations

### Paleta: Atardecer quemado sobre tierra profunda
Tres escaleras:
- **Earth** (neutrales cálidos) — 11 pasos de `#1a0f08` (casi negro corteza) a `#f7e4c9` (crema). Reemplaza los grises por completo.
- **Ember** (acento primario) — `#b8491f` como ★. Lleva CTAs, links, estados activos.
- **Wheat** (secundario) — `#c79828` mostaza. Badges destacados, tips, "featured".
- **Sage** (soporte) — el único no-cálido; `#6b6a3a` oliva profundo. Para `success` y algo de equilibrio.
- **Paper** — `#f2e4c9` como superficie alternativa cálida (editorial, paper cards, about).

Default **dark mode**: `--bg-0: earth-950`, `--fg-1: earth-50`. El light mode es "paper" — no un blanco frío.

### Tipografía: tres voces
| Rol | Familia | Cuándo |
|---|---|---|
| **Display** | Pixelify Sans (variable 400–700) | H1, H2, H3, números grandes — balance entre pixel y legibilidad |
| **Pixel chrome** | Silkscreen (400/700) | Eyebrows, labels, tags, nav, UI chrome — MAYÚSCULAS siempre |
| **Mono / terminal** | VT323 | Código, forms tipo terminal, números UI |
| **Serif (editorial)** | Newsreader (variable + italic) | Leads, bio, long-reads, cards tipo "paper" |
| **Sans (body)** | Geist (variable) | Body copy, descripciones, UI legible |

**Tracking**: las fuentes pixel necesitan aire. Usa `--tracking-pixel: 0.06em` mínimo, hasta `0.12em` en labels chicas.

**Escala**: 12/14/16/18/22/28/36/48/64/88 — snaps to 4px grid.

### Espaciado
Base 4px. Scale: 4/8/12/16/24/32/48/64/96/128. Todo múltiplo de 4 para mantener el grid pixel.

### Fondos
- **Default**: color plano (`--bg-0` o `--bg-1`). Sin gradientes.
- **Hero / effects**: overlay combinado `.crt` (scanlines 1px/3px, `multiply` 0.45) + `.grain` (warm SVG noise, `overlay` 0.18). Siempre sutiles.
- **Nunca**: gradientes bluish-purple, meshes, blur glows.
- **A veces**: repeating pattern pixel como accent (stripes, dither).

### Bordes + Radii
- **Radii**: casi siempre `0`. `2px` para chips muy pequeños. `999px` (pill) solo para status chips inline.
- **Bordes**: chunky. Default `3px solid var(--border-2)`. Cards pueden ir a `4px`. El color default del border es `earth-950` (el negro corteza) — tiñe todo.

### Sombras
**Solo hard-offset, sin blur.** Como un sello sobre papel.
- `--shadow-1`: `2px 2px 0` — chips pequeños
- `--shadow-2`: `4px 4px 0` — default card
- `--shadow-3`: `6px 6px 0` — hero elements
- `--shadow-ember`: `4px 4px 0 var(--ember-700)` — sobre elementos ember (auto-color-correct)

Todas las sombras usan `earth-950` como base salvo la ember variant.

### Movimiento
- **Transiciones cortas** (90–160ms) con `cubic-bezier(.2,.8,.2,1)`
- **Press**: `translate(+Npx, +Npx)` con `N` = offset de shadow; la sombra se elimina. Sensación de tecla pulsada.
- **Hover**: lift `translate(-2px, -2px)` + sombra más grande; o cambio a color del hover ladder (`--accent-hover`).
- **Scanlines / grain**: estáticos, no animados.
- **Sin bounces, sin spring, sin smooth morphs**. Si algo anima, que sea steppy (`steps(2)` o `steps(3)` a veces).
- **Cursor blink**: `1s steps(2, end)` infinito en inputs activos y terminales.

### Hover / press states
- **Botones**: hover cambia color del ladder (`--accent` → `--accent-hover`). Press: `translate(4px,4px)` + sombra 0.
- **Links**: hover → `--accent-hover`
- **Cards**: hover lifts 2px con sombra expandida
- **Chips**: activo = background ember + texto paper + border earth-950
- **Nav links**: active = border-bottom ember 3px

### Transparencia + blur
**Nunca blur.** La estética pixel no tolera suavizado.
Transparencia usada solo en overlays (CRT scanlines, grain, selección de texto). Backgrounds siempre opacos.

### Imagery
- **Warm**: todas las imágenes tiradas a tonos ámbar/naranja. Si la imagen original es fría, aplicar `mix-blend-mode: multiply` con capa ember.
- **Grain**: toda imagen destacada lleva `.grain` encima en 18% opacity.
- **Pixel art**: cuando se genera, siempre con `image-rendering: pixelated`, en el grid de 4px.

### Cards
- Border `3px` (o `4px` para featured), sombra `4px 4px 0` earth-950
- Header interior: eyebrow en Silkscreen ember + título en Pixelify Sans
- 3 variantes: **default** (dark bg-2), **accent** (ember bg + paper text), **paper** (cream bg + ink text, para editorial)

### Layout rules
- Max width 1280px en desktop, padding lateral 32px
- Nav sticky top, 2px border-bottom earth-900
- Footer siempre border-top 2px + fila compacta pixel

---

## Iconography

### Sistema propio
Set de **24 iconos pixel** hechos a medida en `assets/icons.js`. Todos:
- **16×16 grid** (1 unidad SVG = 1 "pixel")
- **shape-rendering: crispEdges**
- Un solo path, `currentColor` fill
- Helper: `MatereIcon(name, { size: 16|24|32|48, color: 'currentColor' })`

Iconos incluidos: `home · heart · star · search · menu · close · arrow_right · arrow_left · check · plus · sparkle · book · mail · user · settings · folder · moon · sun · download · link · external · github · terminal · flame · pixel_diamond`.

**Regla**: si se necesita un icono nuevo, se dibuja en el mismo grid 16×16. **Nunca** mezclar con iconos de Lucide / Heroicons / etc. — rompe el look pixel.

### Fallback
Si un icono necesario aún no está en el set, **documentar la falta y pedir al usuario que lo agregue** en vez de meter un SVG ajeno al grid.

### Emoji
**Prohibido en UI.** Como reemplazo:
- `●` para status pips (coloreado con semantic colors)
- `★ ✓ ← → ·` permitidos como dingbats decorativos
- Cualquier otra cosa → icono del set

### Logos / assets
- [`assets/matere-mark.svg`](./assets/matere-mark.svg) — mark cuadrado 64×64
- [`assets/matere-mark-large.svg`](./assets/matere-mark-large.svg) — mark 128×128 (hero)
- [`assets/matere-wordmark.svg`](./assets/matere-wordmark.svg) — wordmark "MATERE" pixel horizontal
- [`assets/icons.js`](./assets/icons.js) — set de iconos

---

## UI kits

| Kit | Path | Screens |
|---|---|---|
| **Portfolio** | [`ui_kits/portfolio/`](./ui_kits/portfolio/) | Home · Work · About · Contact |

Ver [`ui_kits/portfolio/README.md`](./ui_kits/portfolio/README.md) para detalles por componente.

---

## Caveats / pending
- **Fuentes** vienen del CDN de Google Fonts (subset latin). Si querés soporte extendido (latin-ext, acentos raros, etc.), avisame.
- **Set de iconos** tiene 24 — probablemente vas a querer más específicos (play/pause, image, camera, calendar, clock, bell…). Avisame qué agregar.
- **No hay dark/light toggle** construido — la paleta default es dark. La alternativa "paper" existe como superficie (se ve en el panel About) pero no como theme global. Si querés full light mode, hay que duplicar semantic tokens.
- **Scanlines + grain** se aplican como clases opcionales (`.crt`, `.grain`). Si los querés siempre, aplicarlos en `<body>`.
