import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Physical direction properties are banned in inline styles; the stylelint config bans them in
// CSS files. SmartCart is RTL-first: use the logical equivalents (marginInlineStart, insetInlineEnd,
// paddingInline, textAlign: "start"). See docs/web.md, "RTL guard".
const PHYSICAL_STYLE_KEYS =
  "/^(left|right|marginLeft|marginRight|paddingLeft|paddingRight|borderLeft.*|borderRight.*|border(Top|Bottom)(Left|Right)Radius|float|clear|scrollMargin(Left|Right)|scrollPadding(Left|Right)|margin-left|margin-right|padding-left|padding-right|border-left.*|border-right.*)$/";
const RTL_MESSAGE =
  "Physical left/right styles break RTL. Use logical properties (marginInlineStart, paddingInline, insetInlineEnd, textAlign: 'start'). See docs/web.md.";

const rtlGuard = {
  files: ["**/*.{ts,tsx,js,jsx,mjs}"],
  rules: {
    "no-restricted-syntax": [
      "error",
      {
        selector: `JSXAttribute[name.name='style'] Property[key.name=${PHYSICAL_STYLE_KEYS}]`,
        message: RTL_MESSAGE,
      },
      {
        selector: `JSXAttribute[name.name='style'] Property[key.value=${PHYSICAL_STYLE_KEYS}]`,
        message: RTL_MESSAGE,
      },
      {
        selector:
          "JSXAttribute[name.name='style'] Property[key.name=/^(textAlign|justifySelf|justifyItems|justifyContent)$/][value.value=/^(left|right)$/]",
        message: RTL_MESSAGE,
      },
      {
        // CSSProperties objects declared outside JSX (const s: CSSProperties = {...}).
        selector: `VariableDeclarator[id.typeAnnotation.typeAnnotation.typeName.right.name='CSSProperties'] Property[key.name=${PHYSICAL_STYLE_KEYS}]`,
        message: RTL_MESSAGE,
      },
    ],
  },
};

const config = [
  ...nextVitals,
  ...nextTs,
  rtlGuard,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "out/**",
      "public/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
      "src/api/types.ts",
    ],
  },
];

export default config;
