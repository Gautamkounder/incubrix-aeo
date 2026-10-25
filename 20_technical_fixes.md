# 20 Prioritized Technical SEO & GEO Fixes for incubrix.com

## GEO & Schema Infrastructure (AI Search Optimization)
1. **Implement `/llms.txt`:** Add an `llms.txt` file to the root directory outlining the API, features, and pricing for LLM crawlers (ChatGPT, Perplexity).
2. **Organization Schema:** Inject `@type: Organization` JSON-LD on the homepage linking social profiles (`sameAs`) and official URLs to establish Knowledge Graph entity.
3. **FAQPage Schema:** Add `@type: FAQPage` JSON-LD to the homepage targeting "What is IncuBrix?" and "Supported platforms?" to capture AI answer boxes.
4. **SoftwareApplication Schema:** Add structured data to the `/product` page detailing pricing tiers, operating system (Web), and application category (BusinessApplication) to rank in app directories.
5. **VideoObject Schema:** Add `@type: VideoObject` to all embedded demo videos, including transcript text, upload date, and thumbnail URL for Google Video indexing.
6. **BreadcrumbList Schema:** Implement structured breadcrumbs across all subpages (e.g., Home > Features > Repurposer) to clarify site hierarchy for crawlers.

## Crawlability & Architecture
7. **Optimize `robots.txt`:** Update `robots.txt` to explicitly allow AI crawlers (`GPTBot`, `ClaudeBot`, `PerplexityBot`) while disallowing internal search parameter URLs (`/*?search=`).
8. **Dynamic XML Sitemap:** Generate an auto-updating `sitemap.xml` splitting URLs by type (Pages, Blog, Features) and submit it via Google Search Console API.
9. **Canonical Tags:** Implement self-referencing `<link rel="canonical">` tags on all core pages to prevent duplicate content penalization from UTM parameters.
10. **Fix Broken Internal Links:** Run a PowerShell script to audit and replace all 404-ing internal links (e.g., outdated `/pricing-old` links pointing to the homepage).
11. **Custom 404 Routing:** Replace the default 404 page with a custom routing page that offers immediate search functionality and links to the 3 most popular features.

## On-Page & Performance (Lighthouse)
12. **Resolve Render-Blocking Resources:** Defer non-critical JavaScript (`<script defer>`) and inline critical CSS to improve First Contentful Paint (FCP).
13. **Image Format Upgrades (WebP):** Convert all heavy PNG/JPEG assets to WebP format, reducing payload size by up to 70% for faster mobile loads.
14. **Lazy Loading:** Add `loading="lazy"` attributes to all images below the fold (especially on the heavy `/features` page).
15. **Missing Alt Attributes:** Audit and inject descriptive `alt` text for all feature icons and screenshots, explicitly using target keywords (e.g., "AI content repurposing dashboard").
16. **Tap Target Sizing:** Increase mobile tap targets for the top navigation menu to a minimum of 48x48 pixels to resolve Lighthouse Accessibility warnings.
17. **H1 Tag Deduplication:** Ensure the homepage and landing pages only have exactly one `<h1>` tag; downgrade secondary hero text to `<h2>`.
18. **Meta Description Rewrites:** Rewrite meta descriptions for all feature pages to include a direct call-to-action and primary keyword, keeping under 155 characters.
19. **Open Graph / Twitter Cards:** Implement `og:image`, `og:title`, and `twitter:card` meta tags to ensure links shared on LinkedIn, Discord, and X unfurl with high-conversion preview images.
20. **Contrast Ratio Fixes:** Increase the color contrast ratio of secondary gray text on the pricing page to meet WCAG AA standards (minimum 4.5:1).
