import { z } from "zod";

// Zod probes `new Function("")` to enable its JIT. Our CSP blocks eval, so the probe
// fails quietly but the browser still reports a CSP violation on every page.
// Our payloads are small; the non-JIT path is plenty fast.
z.config({ jitless: true });
