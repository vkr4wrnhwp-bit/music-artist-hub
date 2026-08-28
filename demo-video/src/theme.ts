import { brand } from './brand.config';

export const c = brand.colors;
export const f = brand.fonts;

/** one type scale, used everywhere */
export const type = {
  eyebrow: { fontFamily: f.mono, fontSize: 24, letterSpacing: '0.18em', textTransform: 'uppercase' as const, fontWeight: 500 },
  headline: { fontFamily: f.display, fontSize: 76, lineHeight: 1.04, letterSpacing: '-0.02em', fontWeight: 700 },
  headlineSm: { fontFamily: f.display, fontSize: 52, lineHeight: 1.08, letterSpacing: '-0.015em', fontWeight: 600 },
  why: { fontFamily: f.body, fontSize: 30, lineHeight: 1.42, fontWeight: 400 },
  caption: { fontFamily: f.mono, fontSize: 20, letterSpacing: '0.1em', textTransform: 'uppercase' as const },
};

/** motion: everything eases the same way so the film feels of one hand */
export const EASE = [0.22, 0.61, 0.36, 1] as const;
