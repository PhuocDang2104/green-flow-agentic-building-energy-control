You are a senior creative frontend engineer and motion designer. Build a premium animated landing page for the GreenFlow project inside the existing frontend app.

The landing page must look and feel like the provided reference screenshot: clean white/soft-green background, centered pill navbar, GreenFlow logo, elegant typography, large cinematic 3D Earth visual, 3D chart assets, soft shadows, rounded cards, and high-end product storytelling.

The final result must not feel like a normal scrolling website. It must feel like a slide-based cinematic landing experience: one wheel/touch/keyboard action moves exactly one page forward or backward, with smooth timeline animation between pages.

## 1. Tech stack and libraries

Use the existing React/Next.js frontend structure if present. If the project is Next.js App Router, implement the page at:

`web/app/landing/page.tsx`

If the project uses another router, adapt cleanly but keep all components modular.

Use these packages:

* `three`
* `@react-three/fiber`
* `@react-three/drei`
* `gsap`
* `@gsap/react`

Do not use video for the Earth. The Earth must be a real WebGL 3D object created with Three.js / React Three Fiber.

Use GSAP Observer for the one-scroll-one-section navigation. Do not rely on native browser scroll as the main navigation. Body should be `overflow: hidden` on desktop. Every wheel/touch/keyboard interaction should trigger `goToSection(nextIndex)` or `goToSection(prevIndex)` with cooldown/lock while animation is running.

Support keyboard navigation:

* ArrowDown / PageDown / Space → next section
* ArrowUp / PageUp → previous section
* Home → first section
* End → last section

On mobile, support swipe up/down. For very small screens, allow a graceful fallback but still preserve the snap/slide feeling.

Respect `prefers-reduced-motion`: if enabled, reduce animation duration and disable intense camera movement, bloom flashes and particle bursts.

## 2. Visual direction

Use a premium GreenFlow brand style:

* Background: off-white / soft paper white, not pure white
* Primary green: deep GreenFlow green
* Secondary green: fresh leaf green
* Accent: cyan/blue for Earth and energy
* Text: near-black with green emphasis
* Cards: white or very pale green with thin green border
* Shadows: soft, wide, realistic
* Corners: rounded 14–24px
* Overall: clean, futuristic, sustainable, commercial-building intelligence

Suggested CSS variables:

```css
:root {
  --gf-green: #007a3d;
  --gf-green-dark: #00582d;
  --gf-green-soft: #eaf7ef;
  --gf-leaf: #65bd45;
  --gf-cyan: #16a6c7;
  --gf-ink: #111713;
  --gf-muted: #5f6f65;
  --gf-bg: #f8fbf6;
  --gf-card: rgba(255,255,255,0.86);
  --gf-border: rgba(0,122,61,0.22);
}
```

Typography should feel close to the reference:

* Large serif or editorial headline for selected big statements if available.
* Otherwise use a polished sans-serif with italic green emphasis.
* Use italic green emphasis for key phrases like `all-in-one`, `global-scale`, `everyday operations`, `intense and unstable`, `Clear action is not`.

## 3. Assets to use

Use these existing assets from the public folder:

```txt
web/public/assets/landing/HVAC_light_pie.png
web/public/assets/landing/HVAC_Lighting_bar.png
```

In React/Next image paths, reference them as:

```txt
/assets/landing/HVAC_light_pie.png
/assets/landing/HVAC_Lighting_bar.png
```

Also search the same folder for:

```txt
wmo_article_paper_texture_shadow_3x4.png
WMO article image
ElNino article image
greenflow logo
building render
```

If a WMO article image exists, use it in section 5. If not, create a placeholder component named `WmoArticleCard` with a warning comment and use the available image path once added.

Do not render the reference screenshot itself as the final page. Recreate the layout and animation from it.

## 4. Overall page structure

The landing page has 7 full-screen sections:

1. Hero / Earth intro
2. Global energy challenge
3. Commercial building controllable loads
4. Hanoi commercial building energy breakdown
5. El Niño heat risk article
6. Key problem synthesis
7. Final CTA / GreenFlow solution

Every section should be `100vw x 100vh`. The UI should feel like a slide deck. Each section should have enough whitespace and a clear visual composition.

Use one fixed floating navbar at the top center, styled like the reference:

* left: GreenFlow logo
* nav items: Problem, Agents, Impacts
* right: light/dark mode toggle with sun/cloud style

The navbar remains fixed across all sections and updates active item depending on section.

## 5. Required scroll behavior

Implement a component:

`components/landing/FullPageController.tsx`

Behavior:

* Keep `activeSection` state from 0 to 6.
* Use GSAP Observer to listen to wheel/touch/pointer.
* On scroll down, call `goToSection(activeSection + 1)`.
* On scroll up, call `goToSection(activeSection - 1)`.
* Lock input while the GSAP timeline is running.
* Duration between sections: around 1.1s to 1.6s.
* Ease: use cinematic easing such as `power3.inOut`, `expo.inOut`, or `sine.inOut`.
* Do not allow half-scroll states.
* Every transition must feel like a page flip / stage change, not a webpage scroll.

Implementation style:

* Sections can be absolutely stacked in a `.stage`.
* The active section fades/slides/scales in.
* The previous section exits with slight blur/scale.
* Shared visuals like Earth, charts, and article cards should animate across sections using fixed wrappers and GSAP transforms.

Use a section progress indicator on the right or bottom: 7 small dots or slim vertical markers.

## 6. Shared 3D Earth system

Create:

```txt
components/landing/EarthScene.tsx
components/landing/EarthObject.tsx
components/landing/EarthBuildings.tsx
components/landing/EarthGrid.tsx
components/landing/AtmosphereGlow.tsx
```

The Earth must be built with React Three Fiber:

* `Canvas`
* `SphereGeometry`
* `TextureLoader` or Drei `useTexture`
* Earth day texture
* cloud texture
* normal/bump map
* optional specular/city light/grid texture
* atmosphere glow
* rim light
* directional light
* point light
* subtle particle layer
* slow rotation using `useFrame`

The Earth is not a video. It must be animated in real time.

### Light mode Earth

In light mode:

* Natural bright Earth texture
* Blue ocean, white clouds
* Soft atmosphere glow
* Multiple cloud layers rotating at slightly different speeds
* Tiny stylized building/city elements on top of the globe, like small extruded buildings or pins
* Sustainable/smart-city feeling
* Gentle cinematic rotation
* Soft green-blue lighting

### Dark mode Earth

In dark mode:

* Darker Earth material
* Grid texture / energy network texture
* City lights
* Data lines wrapping around the globe
* Small glowing particles
* Stronger bloom/glow feeling
* Futuristic digital planet feeling
* Keep the same Earth object but smoothly animate material opacity/color/intensity when toggling mode

Theme toggle must not instantly swap the scene. Animate the transition:

* Earth day texture fades slightly down
* grid/city lights fade up
* atmosphere glow becomes more electric
* background changes from warm white to dark green/navy
* particle opacity increases

## 7. Earth positioning across sections

The Earth must feel like one continuous object traveling through the landing page.

Use a fixed wrapper around the Canvas, for example:

```tsx
<div className="earth-stage">
  <EarthScene theme={theme} section={activeSection} />
</div>
```

Animate this wrapper or the Earth group according to section:

### Section 1 — Hero

Earth is huge and cinematic. It sits in the lower half/right side like the reference, partly cropped by the bottom edge.

Position idea:

* `x: 0%`
* `y: 22%`
* `scale: 1.25`
* opacity: 1
* camera slightly close
* clouds visible
* tiny building elements subtle

Text centered above Earth:

```txt
The all-in-one platform
for building intelligence
```

The phrase `all-in-one` must be green italic.

### Transition 1 → 2

On scroll down, the Earth moves down and to the right, becoming smaller. It should feel like the same globe travels into the next slide.

Animate:

* wrapper x: from center/lower to right side
* wrapper y: slightly lower
* scale: from large to medium
* rotate/camera parallax slightly
* text from section 1 fades upward
* section 2 statistic cards enter from left

### Section 2 — Global energy challenge

Layout like reference:

* Left side: text and stats
* Right side: smaller Earth sphere

Copy:

```txt
Commercial buildings are
a global-scale energy challenge
```

`global-scale` should be green italic.

Stats:

* `30%`

  * Commercial and non-residential buildings account for around 30% of global building final energy demand.
* `38.6 EJ`

  * Energy used by commercial and non-residential buildings globally in 2019.
* `~10,700 TWh`

  * That is enough energy to power Singapore for about 185 years.

Cards must look like the reference: pale green, rounded, icon on the left, number bold, explanation smaller.

### Transition 2 → 3

The Earth should zoom forward and create a white/cloud wipe. This is the most cinematic transition.

Animation idea:

* Earth scale increases quickly
* Cloud layer opacity increases
* Screen becomes white/soft mist for 300–500ms
* Then a 3D commercial building/urban block appears from the center/bottom
* Two chart images appear from left/right
* Use mask/clip-path reveal and depth shadow

### Section 3 — Key controllable loads

Layout like reference:

* Left: text and load cards
* Right: 3D building + two chart assets floating

Copy:

```txt
Inside commercial buildings, the biggest energy
loads come from everyday operations.
```

`everyday operations` green italic.

Left card title:

```txt
Key controllable loads
```

Include four icon rows:

* Lighting
* Heating
* Ventilation
* Air Condition

Use simple line icons in green. Use `lucide-react` if already installed. If not, create minimal inline SVG icons.

Right side:

* Use `/assets/landing/HVAC_light_pie.png`
* Use `/assets/landing/HVAC_Lighting_bar.png`
* Add a stylized 3D building render/illustration in front or center.
* If no building asset exists, create a CSS/HTML 3D building block with vertical windows and perspective, but prefer existing asset if available.
* Charts should float with slight 3D tilt and shadow.
* Add slow parallax based on mouse movement.

### Transition 3 → 4

The pie chart must become the hero object.

Animation:

* `/assets/landing/HVAC_light_pie.png` starts on the right in section 3.
* It scales up, moves diagonally, and lands on the left side of section 4.
* Bar chart fades/slides backward and becomes secondary or disappears.
* Building recedes with blur/scale down.
* 70% insight card appears on the right.

### Section 4 — Hanoi commercial buildings energy breakdown

Layout like reference:

* Left: large 3D pie chart image
* Right: large 70% card

Use the pie chart image:

```txt
/assets/landing/HVAC_light_pie.png
```

Right card content:

```txt
Zooming into Ha Noi commercial buildings, HVAC
and lighting together represent

70%

of end-use energy consumption.
```

Style:

* Card background: white with soft green tint
* Thin green border
* Very large `70%`
* Add subtle mini bar ghost illustration inside card
* Add small vertical pill icon on the right
* Animate the 70% number counting from 0 to 70 when entering section

Important: The pie chart image already contains data labels. Keep it clear, sharp, and not blurred. Do not stretch it badly. Use `object-fit: contain`.

### Transition 4 → 5

The 70% box/card moves to the left and transforms into a vertical stack of climate/comfort metric cards.

The WMO article image appears on the right with a paper-card animation.

Animation:

* Section 4 card compresses/slides left
* It becomes/gets replaced by 3 metric cards
* Article image enters from right with rotationY and shadow
* Article settles with a slight paper texture and drop shadow
* Add a soft warm-red ambient glow behind the article to echo heat risk

### Section 5 — El Niño heat risk

Layout like reference:

* Left: headline + three metric cards
* Right: WMO article card image

Copy:

```txt
El Niño makes urban heat more
intense and unstable.
```

`intense and unstable` green italic.

Metric cards:

1. `41.3°C`

   * recorded in Hanoi during the May 2023 heatwave
2. `24–27°C`

   * typical indoor comfort range maintained by air conditioning in Vietnamese office buildings
3. `14–17°C`

   * this sudden cooling is proven to trigger thermal discomfort, fatigue and headaches

Right side:

* Use the WMO article/card image from `/assets/landing/` if present.
* Preferred filename:
  `/assets/landing/wmo_article_paper_texture_shadow_3x4.png`
* If not found, create a card placeholder with the same layout and use the uploaded WMO article image when available.

Animation details:

* Article floats in with `rotateZ(-2deg)` then settles to 0
* Paper card has shadow, slight texture, and depth
* Metric cards enter one by one with icons
* Add subtle animated heatwave lines in the background
* On dark mode, article remains readable but background becomes dark green/navy

### Transition 5 → 6

The article fades/scales back. Data cards and problem statement come forward.

Animation:

* Article moves right and fades to 0.2 then disappears
* Metric cards collapse into smaller icons
* Large centered text appears
* Problem cards slide up from bottom with stagger

### Section 6 — Key problem synthesis

Center headline:

```txt
Data is everywhere.
Clear action is not.
```

`Clear action is not.` green italic.

Main large card:

Title:

```txt
Key Problem
```

Body:

```txt
Building owners and facility managers need a reliable way to reduce energy waste and operating costs while keeping occupants safe during extreme weather.
```

Below main card, show 3 smaller cards:

1. `Too much data not enough action`
2. `Operating costs keep rising`
3. `Extreme weather puts occupants at risk`

Animation:

* Headline split-line reveal
* Main card grows from 0.96 to 1
* Three small cards stagger upward
* Icons draw themselves using SVG stroke animation
* Background has faint grid/leaf line art

### Transition 6 → 7

Move from problem to solution.

Animation:

* Problem cards slide down/fade
* CTA copy enters from left
* Building visual enters from right with upward motion
* Small AI/energy labels float around building
* GreenFlow logo/leaf icon animates in the headline

### Section 7 — Final CTA

Layout like reference:

Left side:

```txt
Smarter building operations
start with greenflow
```

`start with` green italic. Include GreenFlow leaf icon before/near `greenflow`.

Subtitle:

```txt
An AI-powered building intelligence platform for reducing energy waste without compromising comfort.
```

CTA button:

```txt
Enter Demo →
```

Right side:

* Premium 3D green commercial building render
* If asset exists, use it.
* If no asset exists, create a stylized CSS/Three.js building card.
* Add floating labels:

  * `Energy Waste -28%`
  * `AI Optimization Active`
  * `Comfort Score 92% Excellent`
  * small `AI` bubble
* Building should have soft ground shadow, green facade accents, small trees, and clean product-marketing look.

Animation:

* CTA button has magnetic hover effect
* Building has subtle float
* Labels animate gently
* On hover, labels slightly move and glow
* `Enter Demo` button should navigate to the existing app/demo route if available. Search the repo for dashboard/demo route. If not found, use `href="/demo"` and add TODO comment.

## 8. Component architecture

Create these files if the project structure allows:

```txt
web/components/landing/LandingExperience.tsx
web/components/landing/FullPageController.tsx
web/components/landing/GreenflowNav.tsx
web/components/landing/EarthScene.tsx
web/components/landing/EarthObject.tsx
web/components/landing/SectionHero.tsx
web/components/landing/SectionGlobalEnergy.tsx
web/components/landing/SectionControllableLoads.tsx
web/components/landing/SectionHanoiBreakdown.tsx
web/components/landing/SectionElNino.tsx
web/components/landing/SectionProblem.tsx
web/components/landing/SectionFinalCTA.tsx
web/components/landing/MagneticButton.tsx
web/components/landing/AnimatedNumber.tsx
web/components/landing/FloatingChart.tsx
web/components/landing/MetricCard.tsx
web/components/landing/useFullPageNavigation.ts
web/components/landing/useMouseParallax.ts
web/styles/landing.css
```

If the repo uses Tailwind, you can use Tailwind classes, but still create a dedicated CSS module or CSS file for complex animations.

## 9. Animation requirements

Use GSAP timelines. Avoid random CSS-only transitions for major section changes.

Each transition should have:

* exit animation for current section
* shared object movement if applicable
* enter animation for next section
* staggered child reveal
* input lock until complete

Suggested durations:

* Section transition base: 1.2s
* Text reveal: 0.5–0.8s
* Card stagger: 0.12–0.18s between cards
* Earth movement: 1.2–1.6s
* Cloud wipe: 0.4–0.7s
* Chart hero move: 1.1–1.4s

Easing:

* `power3.inOut`
* `expo.inOut`
* `sine.inOut`
* `back.out(1.4)` for small card pops only

Do not overuse bouncing effects. The tone should be premium, not cartoonish.

## 10. Advanced creative details

Add these high-end details:

### Mouse parallax

Cards, article, chart images, and Earth wrapper should respond subtly to mouse movement.

* max translate: 8–18px
* max rotate: 1–3 degrees
* disable on mobile and reduced motion

### Magnetic CTA button

The final CTA button should slightly follow the cursor and return smoothly.

### Split headline reveal

Use line masks for big text. Each headline line should reveal upward through overflow hidden.

### Section background transitions

* Section 1: clean white with soft blue/green glow behind Earth
* Section 2: white/soft green
* Section 3: white with cloud mist transition
* Section 4: pale green energy-dashboard background
* Section 5: white with subtle warm heat gradient behind article
* Section 6: white/paper with faint data grid
* Section 7: bright optimistic white-green

### Floating particles

Only around the Earth and final building. Keep subtle. Do not cover text.

### Cloud wipe

Implement a full-screen translucent cloud/mist overlay for transition 2 → 3. It should be animated with blur, opacity, and scale. It should not stay visible after section 3 finishes entering.

### Dark mode

Dark mode must affect:

* background
* navbar
* cards
* text
* Earth material
* grid/city light layer
* particle visibility

Keep all charts and article readable in dark mode by putting them on white cards.

## 11. Performance requirements

* Use `next/image` where possible for static images.
* For R3F Canvas, set DPR to `[1, 1.5]` or `[1, 2]`, not unlimited.
* Lazy load heavy 3D assets.
* Use compressed textures if available.
* Pause unnecessary animations when not visible.
* Do not create multiple WebGL canvases per section. Use one shared Earth Canvas.
* Keep chart images as optimized PNG/WebP.
* Run `npm run build` successfully.
* Fix TypeScript and lint issues.

## 12. Accessibility and UX

* All meaningful images need alt text.
* Keyboard navigation must work.
* The section indicator should have accessible labels.
* Reduced motion mode must be respected.
* Text contrast must remain readable in light and dark mode.
* Do not trap focus badly. CTA and nav should remain usable.

## 13. Implementation details for the one-scroll navigation

Pseudo-logic:

```ts
const [active, setActive] = useState(0)
const isAnimating = useRef(false)

function goToSection(next: number) {
  if (isAnimating.current) return
  if (next < 0 || next > sections.length - 1) return

  isAnimating.current = true

  const tl = gsap.timeline({
    defaults: { ease: 'power3.inOut' },
    onComplete: () => {
      setActive(next)
      isAnimating.current = false
    }
  })

  // animate current section out
  // animate shared Earth/chart/article wrappers
  // animate next section in
}
```

Use `gsap.context()` or `useGSAP()` for cleanup.

Use Observer:

```ts
Observer.create({
  target: window,
  type: 'wheel,touch,pointer',
  wheelSpeed: -1,
  tolerance: 12,
  preventDefault: true,
  onDown: () => goToSection(active + 1),
  onUp: () => goToSection(active - 1),
})
```

Adapt exact direction if needed after testing.

## 14. Exact section copy

Use this copy unless there is already better copy in the repo.

### Section 1

```txt
The all-in-one platform
for building intelligence
```

### Section 2

```txt
Commercial buildings are
a global-scale energy challenge
```

Stats:

```txt
30%
Commercial and non-residential buildings account for around 30% of global building final energy demand.

38.6 EJ
Energy used by commercial and non-residential buildings globally in 2019.

~10,700 TWh
That is enough energy to power Singapore for about 185 years.
```

### Section 3

```txt
Inside commercial buildings, the biggest energy
loads come from everyday operations.
```

Card title:

```txt
Key controllable loads
```

Loads:

```txt
Lighting
Heating
Ventilation
Air Condition
```

### Section 4

```txt
Zooming into Ha Noi commercial buildings, HVAC
and lighting together represent

70%

of end-use energy consumption.
```

### Section 5

```txt
El Niño makes urban heat more
intense and unstable.
```

Metric cards:

```txt
41.3°C
recorded in Hanoi during the May 2023 heatwave

24–27°C
typical indoor comfort range maintained by air conditioning in Vietnamese office buildings

14–17°C
this sudden cooling is proven to trigger thermal discomfort, fatigue and headaches
```

### Section 6

```txt
Data is everywhere.
Clear action is not.
```

Problem card:

```txt
Key Problem

Building owners and facility managers need a reliable way to reduce energy waste and operating costs while keeping occupants safe during extreme weather.
```

Small cards:

```txt
Too much data not enough action
Operating costs keep rising
Extreme weather puts occupants at risk
```

### Section 7

```txt
Smarter building operations
start with greenflow

An AI-powered building intelligence platform for reducing energy waste without compromising comfort.

Enter Demo →
```

Floating labels:

```txt
Energy Waste -28%
AI Optimization Active
Comfort Score 92% Excellent
AI
```

## 15. Visual matching checklist

The final landing page should match the reference in spirit:

* Top pill navbar centered
* GreenFlow branding
* White/green clean background
* Large Earth on first slide
* Earth shrinks to right on second slide
* Third slide introduces commercial building + charts
* Pie chart becomes large on fourth slide
* 70% card appears on fourth slide
* El Niño article appears on fifth slide
* Problem synthesis on sixth slide
* Final CTA with building on seventh slide
* Smooth one-scroll page transition
* Premium shadows and high-resolution assets
* No cheap default web-scroll feeling

## 16. Build and verification

After implementation:

1. Install missing dependencies.
2. Run the dev server.
3. Verify every section transition with mouse wheel, touchpad, keyboard, and touch.
4. Verify light/dark toggle changes the Earth style.
5. Verify chart images load from:

   * `/assets/landing/HVAC_light_pie.png`
   * `/assets/landing/HVAC_Lighting_bar.png`
6. Verify article image loads if present.
7. Verify `npm run build` passes.
8. Fix any TypeScript, ESLint, hydration, or WebGL SSR issues.
9. For Next.js, make all R3F components client-only with `"use client"` and dynamic import if necessary.
10. Do not leave broken imports or placeholder errors.

Deliver production-quality code, not a rough mockup.
