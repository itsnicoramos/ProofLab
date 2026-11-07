import type { Metadata } from "next";

import { Tex } from "@/components/Rich";

export const metadata: Metadata = { title: "Typing math" };

const ROWS: [string, string, string][] = [
  ["2x,  3(x+1),  x sin x", "2x,\\ 3(x+1),\\ x\\sin x", "Multiplication can be implied"],
  ["x^2,  x**2,  x²", "x^2", "Powers"],
  ["sqrt(x),  √x,  cbrt(x)", "\\sqrt{x},\\ \\sqrt[3]{x}", "Roots"],
  ["sin x,  sin(2x),  sin^2(x)", "\\sin x,\\ \\sin 2x,\\ \\sin^2 x", "Trig, with or without brackets"],
  ["sin^-1(x),  arcsin(x)", "\\arcsin x", "Inverse trig"],
  ["ln(x)", "\\ln x", "Natural log"],
  ["log(x)", "\\log_{10} x", "Base-10 log, like a calculator"],
  ["log_2(x),  log(x, 2)", "\\log_2 x", "Other bases"],
  ["e^x,  exp(x)", "e^x", "e is always Euler's number"],
  ["pi,  π", "\\pi", ""],
  ["oo,  inf,  ∞", "\\infty", "Infinity (also for limits)"],
  ["|x|,  abs(x)", "|x|", "Absolute value"],
  ["n!", "n!", "Factorial"],
  ["int(f, x),  int(f, x, a, b)", "\\int f\\,dx,\\ \\int_a^b f\\,dx", "Integrals, in integration steps"],
];

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Typing math</h1>
        <p className="text-muted">
          Type math the way you would on a calculator. After each check, ProofLab shows how it read
          every step, so you can catch typos like <code className="font-mono">1/2x</code> (which
          means <Tex latex="\tfrac{1}{2}x" />, not <Tex latex="\tfrac{1}{2x}" />).
        </p>
      </header>

      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line text-sm text-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">Type</th>
              <th className="px-4 py-2.5 font-medium">Means</th>
              <th className="px-4 py-2.5 font-medium">Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {ROWS.map(([typed, latex, note]) => (
              <tr key={typed}>
                <td className="whitespace-nowrap px-4 py-2.5 font-mono">{typed}</td>
                <td className="whitespace-nowrap px-4 py-2.5">
                  <Tex latex={latex} />
                </td>
                <td className="px-4 py-2.5 text-muted">{note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="space-y-3 text-sm">
        <h2 className="text-lg font-semibold">Steps</h2>
        <ul className="list-disc space-y-1.5 pl-5 text-muted">
          <li>
            One idea per line. Press <kbd className="font-mono">Enter</kbd> for a new step and{" "}
            <kbd className="font-mono">⌘/Ctrl + Enter</kbd> to check.
          </li>
          <li>
            Labels are fine: <code className="font-mono">f&apos;(x) = 2x</code> and{" "}
            <code className="font-mono">dy/dx = 2x</code> are read as <Tex latex="2x" />.
          </li>
          <li>
            Some problems have special step kinds, such as <b>Let</b> and <b>Witness</b> in proofs,{" "}
            <b>L&apos;Hôpital</b> in limits, or <b>Test</b> in series. Pick them from the menu at the
            start of the step.
          </li>
          <li>Only the problem&apos;s own variables (and constants like C) are allowed.</li>
        </ul>
      </section>
    </div>
  );
}
