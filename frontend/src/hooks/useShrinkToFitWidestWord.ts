import { useLayoutEffect, useState } from 'react';
import type { RefObject } from 'react';

// Shrinks a title/body span's font-size (never its box) just enough that its
// single widest word fits the available text column, so the browser's
// `overflow-wrap: break-word` fallback never has to chop a word mid-syllable
// ("Warehous" / "e").
//
// Deliberately a pure text-rendering tweak: it never touches node.width/
// height/style.width/style.height or the box the wrapper occupies (it stays
// whatever React Flow measured), so it cannot perturb React Flow's
// measured-size bookkeeping the way changing computeNodeDimensions's output
// did (see layoutCore.ts's computeNodeDimensions doc comment for that
// history/regression).
//
// CSS `hyphens: auto` was tried first as a zero-JS alternative but doesn't
// actually break "Warehouse" at a syllable boundary in Chromium (verified
// empirically -- the property parses and `getComputedStyle` reports
// 'auto', but headless Chromium here still hard-splits the word).
//
// A Canvas 2D `measureText()`-based approach was tried next (and is what
// CylinderNode.tsx originally shipped with) but proved unreliable under
// live-render verification in two independent ways once exercised against
// a bold, letter-spaced title ("Extraordinarily" under PanelNode's
// `tracking-widest` + `font-extrabold`, in an 81px column):
//   1. `measureText()` ignores CSS `letter-spacing` entirely, so any
//      tracked title (every title/body span here uses some Tailwind
//      `tracking-*` utility) was silently under-measured by
//      `(word.length - 1) * letterSpacingPx`.
//   2. Independent of that, `ctx.font = "800 Npx Inter"` did not reliably
//      resolve to the same glyphs the DOM actually painted -- measured
//      width for the identical text/weight/size varied across runs
//      (~74px vs ~82px) depending on whether that exact family/weight had
//      already been used elsewhere on the page, and even once stabilized
//      via `document.fonts.load(...)`, still measured ~30% narrower than
//      the word's real rendered width. Chromium's canvas font matching
//      just doesn't reliably mirror DOM layout's font resolution for this
//      weight/family combination.
// Both gaps compounded: even after explicitly compensating for
// letter-spacing, the title still measured comfortably "fits" while the
// live render kept mid-word-breaking it -- confirmed repeatedly via real
// Playwright screenshots, not just failing quietly.
//
// So this measures with a real, hidden DOM element instead: a clone
// carrying the exact same resolved font-family/weight/style/letter-spacing
// as the actual span, rendered (off-screen) by the same layout engine that
// renders the title itself. That makes every one of the above gaps
// structurally impossible -- there is no separate "measurement API" to
// disagree with the real render, because the measurement *is* a real
// render, of the same word, at the same computed font, one throwaway DOM
// node away from the reader's screen. Switching measurement technique
// still wasn't the whole story, though: the DOM probe *also* under-measured
// PanelNode's title at first, because the probe wasn't given
// `text-transform` -- PanelNode's title is `uppercase`, and capital
// letters are meaningfully wider than the mixed-case source string in most
// typefaces, so the probe was quietly measuring "Extraordinarily" while
// the real title painted "EXTRAORDINARILY". Copying `text-transform` onto
// the probe (letting the browser apply the same transform to the same
// characters, rather than upper-casing the JS string ourselves) closed
// that last gap -- confirmed by a live screenshot showing the title
// finally holding to one line at the resulting font size.
//
// Originally implemented in CylinderNode.tsx (canvas-based); extracted and
// switched to DOM-probe measurement here so CardNode, CloudNode,
// EllipseNode, InputNode, LabelNode, and PanelNode can share the fix.
// (DecisionNode/diamond already has its own independent length-based
// font-scaling + line-clamp and doesn't need this.)

let probeEl: HTMLSpanElement | null = null;
function getProbeEl(): HTMLSpanElement | null {
  if (typeof document === 'undefined') return null;
  if (!probeEl) {
    const el = document.createElement('span');
    el.style.position = 'absolute';
    el.style.visibility = 'hidden';
    el.style.pointerEvents = 'none';
    el.style.whiteSpace = 'pre';
    el.style.top = '-9999px';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    probeEl = el;
  }
  return probeEl;
}

/**
 * Renders `word` in a hidden clone of `sourceStyle` at `fontPx` and returns
 * its real rendered width.
 *
 * `text-transform` matters here as much as the font properties: PanelNode's
 * title is `uppercase`, and capital letters are meaningfully wider than
 * their mixed-case originals in most typefaces -- a probe that copied
 * font-family/weight/style/letter-spacing but not text-transform measured
 * the *un-transformed* "Extraordinarily" (correctly matching every other
 * node type, none of which transform case) while PanelNode actually
 * painted "EXTRAORDINARILY", silently under-measuring by exactly the
 * amount that turned out to still overflow and mid-word-break the real
 * render. Setting text-transform on the probe lets the browser apply the
 * same case transform to the same characters, so the glyphs it measures
 * are the same glyphs it paints -- no need to transform the JS string.
 */
function measureWordPx(sourceStyle: CSSStyleDeclaration, word: string, fontPx: number): number {
  const probe = getProbeEl();
  if (!probe) return 0;
  probe.style.fontFamily = sourceStyle.fontFamily;
  probe.style.fontWeight = sourceStyle.fontWeight;
  probe.style.fontStyle = sourceStyle.fontStyle;
  probe.style.letterSpacing = sourceStyle.letterSpacing;
  probe.style.textTransform = sourceStyle.textTransform;
  probe.style.fontSize = `${fontPx}px`;
  probe.textContent = word;
  return probe.getBoundingClientRect().width;
}

/**
 * Font size (px, integer) that fits `text`'s single widest word into
 * `availablePx`, clamped to [minPx, basePx].
 *
 * Starts from a linear estimate (glyph/letter-spacing widths scale
 * ~proportionally with font-size) and then verifies -- and, if the
 * estimate was optimistic, walks down 1px at a time -- with real
 * DOM measurements at the candidate size, so the returned size is
 * confirmed to fit rather than merely projected to.
 */
function fitWidestWordFontSize(
  sourceStyle: CSSStyleDeclaration,
  text: string,
  availablePx: number,
  basePx: number,
  minPx: number
): number {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length || !(availablePx > 0)) return basePx;

  let widestWord = words[0];
  let widestAtBase = 0;
  for (const w of words) {
    const width = measureWordPx(sourceStyle, w, basePx);
    if (width > widestAtBase) {
      widestAtBase = width;
      widestWord = w;
    }
  }
  if (widestAtBase <= availablePx || widestAtBase <= 0) return basePx;

  let candidate = Math.max(minPx, Math.min(basePx - 1, Math.floor((basePx * availablePx) / widestAtBase)));
  while (candidate > minPx && measureWordPx(sourceStyle, widestWord, candidate) > availablePx) {
    candidate -= 1;
  }
  return candidate;
}

export interface ShrinkToFitOptions {
  /**
   * Other elements that share spanRef's immediate parent (an icon, a
   * status dot, a badge, an annotations tray, ...) and eat into the
   * parent's clientWidth without being part of the text column itself.
   * Each ref's live `getBoundingClientRect().width`, plus one instance of
   * the parent's own CSS gap per reserved element, is subtracted from the
   * available width before fitting. Omit when the span's parent is a
   * dedicated text-only column (nothing else to subtract).
   */
  reservedRefs?: Array<RefObject<HTMLElement | null>>;
}

/**
 * Measures `text` against `spanRef`'s parent column width (its clientWidth
 * minus its own padding, minus any `reservedRefs` sibling widths) and
 * returns the font size to apply. The parent must be a container whose
 * rendered width is deterministic -- i.e. not itself inflated by the
 * span's own text length -- which holds when it's capped by an explicit
 * max-width (a shrink-to-fit box in a centered flex-column layout), sized
 * via flex-basis/min-w-0 truncation, or is simply the fixed pixel box
 * React Flow measured for the node. Re-measures whenever `text` changes;
 * box/container size is static per layout run (node dimensions are fixed
 * per-type defaults, see specCompiler.ts / ELK), so no ResizeObserver is
 * needed.
 */
export function useShrinkToFitWidestWord(
  spanRef: RefObject<HTMLElement | null>,
  text: string,
  basePx: number,
  minPx: number,
  options?: ShrinkToFitOptions
): number {
  const [fontSize, setFontSize] = useState(basePx);
  const reservedRefs = options?.reservedRefs;

  useLayoutEffect(() => {
    const el = spanRef.current;
    const parent = el?.parentElement;
    if (!el || !parent || !text) {
      setFontSize(basePx);
      return;
    }

    // Re-derives everything fresh each call (rather than closing over one
    // snapshot) so the deferred re-measure below reflects the DOM as it
    // stands when the font actually finishes loading, not a stale
    // snapshot from the first (possibly pre-font-load) pass.
    const measure = (): number => {
      const parentStyle = window.getComputedStyle(parent);
      const paddingX = parseFloat(parentStyle.paddingLeft || '0') + parseFloat(parentStyle.paddingRight || '0');

      let reservedPx = 0;
      if (reservedRefs && reservedRefs.length) {
        const gapPx = parseFloat(parentStyle.columnGap || '0') || 0;
        for (const reservedRef of reservedRefs) {
          const reservedEl = reservedRef.current;
          if (reservedEl) reservedPx += reservedEl.getBoundingClientRect().width + gapPx;
        }
      }

      const availablePx = parent.clientWidth - paddingX - reservedPx;
      const spanStyle = window.getComputedStyle(el);
      return fitWidestWordFontSize(spanStyle, text, availablePx, basePx, minPx);
    };

    setFontSize(measure());

    // The DOM probe above renders with whatever font is *currently*
    // resolved for spanStyle's family/weight, which -- like the real
    // title -- can still be a temporary fallback face if the real font
    // file hasn't finished loading yet at this exact layout-effect tick.
    // `document.fonts.load(...)` fetches the exact family/weight the span
    // uses (a no-op, already-resolved promise if it's already loaded) and
    // triggers one re-measure once it's actually in, so the result
    // converges to the size measured against the real, final glyphs
    // rather than a possibly-narrower placeholder. This never regresses
    // the box/layout the way changing computeNodeDimensions's output did
    // (see layoutCore.ts's doc comment for that history) -- it only ever
    // calls setFontSize again with a pure function of the (by-then
    // font-accurate) measurement, same shape as the synchronous path
    // above, so there's no risk of the layout-completion signal
    // (`window.__LAYOUT_COMPLETE__`, driven by React Flow's own node
    // measurement -- untouched by this hook) ever waiting on it.
    let cancelled = false;
    const spanStyleForLoad = window.getComputedStyle(el);
    const fontSpec = `${spanStyleForLoad.fontStyle} ${spanStyleForLoad.fontWeight} ${basePx}px ${spanStyleForLoad.fontFamily}`;
    if (typeof document !== 'undefined' && document.fonts && typeof document.fonts.load === 'function') {
      document.fonts.load(fontSpec, text).then(() => {
        if (cancelled) return;
        setFontSize(measure());
      }).catch(() => {
        // Font failed to load (offline, blocked request, ...) -- keep the
        // synchronous best-effort size from above.
      });
    }

    return () => {
      cancelled = true;
    };
    // reservedRefs intentionally excluded: refs are stable identities and
    // this effect already re-measures whenever the text (or size bounds)
    // changes, matching the dependency shape of the original
    // CylinderNode.tsx implementation this hook was extracted from.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, basePx, minPx]);

  return fontSize;
}

export default useShrinkToFitWidestWord;
