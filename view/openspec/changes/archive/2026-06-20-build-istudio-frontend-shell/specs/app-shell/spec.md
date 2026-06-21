# Delta for App Shell

## ADDED Requirements

### Requirement: Three-Region Layout

The home page SHALL render a left chat sidebar (300px fixed), a fluid studio canvas, and a right assets drawer (260px), matching reference.html proportions.

#### Scenario: Default desktop layout

- GIVEN a viewport width of 1280px
- WHEN the home page renders
- THEN the chat sidebar, studio canvas, and assets drawer are visible side by side

#### Scenario: Canvas fills remaining width

- GIVEN a desktop viewport
- WHEN measuring the studio canvas width
- THEN it equals viewport width minus 300px sidebar and 260px drawer

### Requirement: Responsive Assets Drawer

The assets drawer SHALL be collapsed by default on viewports ≤768px and visible by default on viewports ≥1024px.

#### Scenario: Small viewport hides drawer

- GIVEN a viewport width of 375px
- WHEN the page loads
- THEN the assets drawer is not rendered and the canvas uses the full remaining width

#### Scenario: Large viewport shows drawer

- GIVEN a viewport width of 1440px
- WHEN the page loads
- THEN the assets drawer is visible and the canvas width adjusts accordingly

### Requirement: Drawer Toggle

The assets toggle button SHALL reflect drawer state with `aria-expanded` and toggle the drawer's visibility.

#### Scenario: Toggle collapses drawer

- GIVEN the drawer is visible on desktop
- WHEN the user clicks the assets toggle button
- THEN the drawer hides and the button's `aria-expanded` becomes `false`

### Requirement: Region Semantics

The shell SHALL use `<aside aria-label="Agent Chat">` for the chat sidebar, `<main>` for the workspace, `<aside aria-label="Context Assets">` for the drawer, and `<header>`/`<section>` inside regions.

#### Scenario: Accessibility tree exposes regions

- GIVEN the rendered shell
- WHEN an assistive technology requests landmarks
- THEN it finds complementary regions labeled "Agent Chat" and "Context Assets"

### Requirement: Studio Tabs

The top bar SHALL contain a `role="tablist"` with at least one tab "Studio Canvas" using `role="tab"` and `aria-selected`.

#### Scenario: Tablist is present

- GIVEN the rendered workspace header
- WHEN inspected
- THEN the tab container has `role="tablist"` and the active tab has `aria-selected="true"`

### Requirement: Status Announcement

The canvas status text SHALL live in an element with `aria-live="polite"`.

#### Scenario: Status changes are announced

- GIVEN the status reads "GENERATING..."
- WHEN the text changes to "COMPLETED in 12.4s"
- THEN screen readers announce the new text without stealing focus

### Requirement: Reduced Motion

The pulse/scan animation SHALL be disabled when the user prefers reduced motion.

#### Scenario: Reduced motion enabled

- GIVEN `prefers-reduced-motion: reduce` is active
- WHEN the status pulse renders
- THEN it is visually static and no motion is applied

### Requirement: Composer Keyboard Support

The chat composer SHALL send on `Enter` and insert a newline on `Shift+Enter`.

#### Scenario: Enter sends message

- GIVEN focus is in the composer textarea
- WHEN the user presses Enter without Shift
- THEN the composer triggers the send action

#### Scenario: Shift+Enter inserts newline

- GIVEN focus is in the composer textarea
- WHEN the user presses Shift+Enter
- THEN a newline is inserted in the textarea

### Requirement: Timestamps

Message timestamps SHALL use the `<time>` element with a `dateTime` attribute.

#### Scenario: Timestamp is semantic

- GIVEN a message sent at 14:03
- WHEN rendered
- THEN it contains `<time dateTime="14:03">14:03</time>`

### Requirement: Facade-Only Behavior

The shell SHALL use mock data and SHALL NOT persist messages, upload assets, authenticate users, or call backend APIs.

#### Scenario: Send action is a no-op

- GIVEN the composer contains text
- WHEN the user sends the message
- THEN the message list remains unchanged

#### Scenario: Upload button is a no-op

- GIVEN the assets drawer is visible
- WHEN the user clicks "Upload Asset"
- THEN no file dialog opens and no asset is added
