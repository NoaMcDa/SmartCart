### Web build and checks, production export (origin `https://preview.invalid`, `NEXT_PUBLIC_INDEX_UNPRICED=0`)

- `next build`: passed in 23.6 s
- Structured-data validation and SEO unit tests: 118 of 121 passed, **3 failed** (9.6 s)
  - jsonld.test.ts: structured data Product has no offers while no prices are loaded: AssertionError: expected { …(8) } to not have property "offers"     at /home/runner/work/SmartCart/SmartCart/apps/web/src/features/seo/jsonld.test.ts:53:22     at file:///home/runner/work/SmartCart/SmartCart/apps/web/node_modules/vitest/dis
  - pages.test.tsx: category pages (#35) render the Hebrew title, products, update date, methodology link and the checkout line: TestingLibraryElementError: Unable to find an element with the text: /נתוני הקטלוג עודכנו בתאריך/. This could be because the text is broken up by multiple elements. In this case, you can provide a function for your text matcher to make your
  - pages.test.tsx: product pages (#35) without prices say so, carry no offers, and keep the trust lines: TestingLibraryElementError: Unable to find an element with the text: /עדיין לא נטענו מחירים למוצר הזה/. This could be because the text is broken up by multiple elements. In this case, you can provide a function for your text matcher to make
- Crawl of every generated page: 203 pages, 180 URLs in the sitemap, 1870 checks, **0 failed**; HTML median 34,752 B, largest 51,462 B
- Playwright preview spec (390 px, axe): passed in 12.0 s

