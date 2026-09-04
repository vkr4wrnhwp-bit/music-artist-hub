import type { Metadata } from "next";
import { Instrument_Sans, Geist_Mono } from "next/font/google";
import "./globals.css";

/**
 * TWO FACES, BY ROLE.
 *
 * The variables are named for the job, not the family — `--font-voice` and
 * `--font-readout` — for the same reason `--c-platinum` is named for the
 * reading role rather than the hue. A future swap is this file and nothing
 * else; `globals.css` and every component ask for the role.
 *
 * VOICE — Instrument Sans.
 * A grotesk drawn tight and slightly narrow, which is the property a dense
 * operation table needs: at the 10px this app sets its labels, it keeps its
 * counters where a wider face closes them up. It replaced Inter, which is
 * the face this kind of interface reaches for by default — that being the
 * argument against it rather than for it.
 *
 * READOUT — Geist Mono.
 * Every number a machinist could cut to is set in this: dimensions,
 * tolerances, feeds, offsets, G-code. Its digits are unambiguous at 11px and
 * its zero cannot be read as an O, which is not a stylistic preference on a
 * screen showing bore diameters.
 */
const voice = Instrument_Sans({
  variable: "--font-voice",
  subsets: ["latin"],
  display: "swap",
});

const readout = Geist_Mono({
  variable: "--font-readout",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "CANVAS — From concept to cut.",
  description: "Precision manufacturing intelligence. Plan, machine, deliver.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${voice.variable} ${readout.variable} antialiased`}>{children}</body>
    </html>
  );
}
