import { Suspense } from "react";
import Ask from "@/components/ask";
export default function Page() {
  return (
    <Suspense fallback={<p>Opening the analyst…</p>}>
      <Ask />
    </Suspense>
  );
}
