"use client";

import { Button } from "@/components/ui";

export function PrintButton() {
  return (
    <Button variant="primary" onClick={() => window.print()}>
      Print / PDF
    </Button>
  );
}
