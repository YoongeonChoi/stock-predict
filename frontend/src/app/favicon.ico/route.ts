const ICON_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#0f172a"/>
  <path d="M15 43 27 31l8 8 14-18" fill="none" stroke="#38bdf8" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="49" cy="21" r="5" fill="#22c55e"/>
</svg>
`.trim();

export const dynamic = "force-static";

export function GET() {
  return new Response(ICON_SVG, {
    headers: {
      "Cache-Control": "public, max-age=86400",
      "Content-Type": "image/svg+xml; charset=utf-8",
    },
  });
}
