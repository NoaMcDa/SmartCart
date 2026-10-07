import type { ReactNode, SVGProps } from "react";

/**
 * Inline stroke SVG icons copied from the artboards (docs/design/artboards). Never emoji.
 * Decorative by default (aria-hidden); pass `title` to make an icon meaningful on its own.
 * Direction-sensitive icons (chevrons) are named by meaning, not by geometry:
 * ChevronBack points right and ChevronNext points left, because the UI is RTL.
 */
export type IconProps = Omit<SVGProps<SVGSVGElement>, "children"> & {
  size?: number;
  strokeWidth?: number;
  title?: string;
};

function makeIcon(name: string, paths: ReactNode, defaults: { strokeWidth?: number } = {}) {
  function Icon({ size = 20, strokeWidth, title, ...rest }: IconProps) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth ?? defaults.strokeWidth ?? 2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden={title ? undefined : true}
        role={title ? "img" : undefined}
        focusable="false"
        data-icon={name}
        {...rest}
      >
        {title ? <title>{title}</title> : null}
        {paths}
      </svg>
    );
  }
  Icon.displayName = `Icon${name}`;
  return Icon;
}

export const IconLock = makeIcon(
  "lock",
  <>
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </>,
  { strokeWidth: 2.2 },
);

export const IconTag = makeIcon(
  "tag",
  <>
    <path d="M20 12l-8 8-9-9V3h8z" />
    <circle cx="7.5" cy="7.5" r="1.5" />
  </>,
  { strokeWidth: 2.2 },
);

export const IconRefresh = makeIcon(
  "refresh",
  <>
    <path d="M21 12a9 9 0 1 1-3-6.7" />
    <path d="M21 3v6h-6" />
  </>,
  { strokeWidth: 2.2 },
);

export const IconCheck = makeIcon("check", <path d="M20 6L9 17l-5-5" />, { strokeWidth: 3 });

export const IconInfo = makeIcon(
  "info",
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16h.01" />
  </>,
  { strokeWidth: 2.4 },
);

export const IconDiffers = makeIcon("differs", <path d="M5 9h14M5 15h14M16 4l-8 16" />, {
  strokeWidth: 2.4,
});

export const IconClose = makeIcon("close", <path d="M18 6L6 18M6 6l12 12" />, {
  strokeWidth: 2.4,
});

export const IconWarning = makeIcon(
  "warning",
  <>
    <path d="M12 9v4M12 17h.01" />
    <path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
  </>,
  { strokeWidth: 2.2 },
);

export const IconMoon = makeIcon("moon", <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />);

export const IconSun = makeIcon(
  "sun",
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </>,
);

export const IconList = makeIcon(
  "list",
  <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />,
);

export const IconCompare = makeIcon(
  "compare",
  <>
    <path d="M12 3v18M3 7h18" />
    <path d="M6 7l-3 7a3 3 0 0 0 6 0z" />
    <path d="M18 7l-3 7a3 3 0 0 0 6 0z" />
  </>,
);

export const IconBarcode = makeIcon(
  "barcode",
  <path d="M4 6v12M8 6v12M11 6v12M14 6v12M17 6v12M20 6v12" />,
  { strokeWidth: 2.2 },
);

export const IconBell = makeIcon(
  "bell",
  <>
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </>,
);

export const IconUser = makeIcon(
  "user",
  <>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </>,
);

export const IconMic = makeIcon(
  "mic",
  <>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0" />
    <path d="M12 18v3" />
  </>,
);

export const IconClipboard = makeIcon(
  "clipboard",
  <>
    <rect x="5" y="4" width="14" height="17" rx="2" />
    <path d="M9 4V2h6v2" />
    <path d="M9 11h6M9 15h6" />
  </>,
);

export const IconPin = makeIcon(
  "pin",
  <>
    <path d="M12 22s7-7 7-12a7 7 0 0 0-14 0c0 5 7 12 7 12z" />
    <circle cx="12" cy="10" r="2.5" />
  </>,
);

export const IconClock = makeIcon(
  "clock",
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
);

export const IconMap = makeIcon(
  "map",
  <>
    <path d="M9 4l6 2 6-2v14l-6 2-6-2-6 2V6z" />
    <path d="M9 4v14M15 6v14" />
  </>,
);

export const IconMinus = makeIcon("minus", <path d="M5 12h14" />, { strokeWidth: 2.4 });

export const IconShare = makeIcon(
  "share",
  <>
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <path d="M8.6 10.5l6.8-4M8.6 13.5l6.8 4" />
  </>,
);

export const IconPlus = makeIcon("plus", <path d="M12 5v14M5 12h14" />, { strokeWidth: 2.4 });

/** "Back" in RTL: points right. */
export const IconChevronBack = makeIcon("chevron-back", <path d="M9 6l6 6-6 6" />, {
  strokeWidth: 2.2,
});

/** "Next" / "forward" in RTL: points left. */
export const IconChevronNext = makeIcon("chevron-next", <path d="M15 6l-6 6 6 6" />, {
  strokeWidth: 2.4,
});

export const IconCart = makeIcon(
  "cart",
  <>
    <path d="M3 4h2l2.5 11h11L21 7H7" />
    <circle cx="9" cy="20" r="1.5" />
    <circle cx="17" cy="20" r="1.5" />
  </>,
  { strokeWidth: 2.2 },
);

export const IconMonitor = makeIcon(
  "monitor",
  <>
    <rect x="3" y="4" width="18" height="12" rx="2" />
    <path d="M8 20h8M12 16v4" />
  </>,
);
