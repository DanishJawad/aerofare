// A handful of inline stroke icons, so the app doesn't need an icon library.
// All are decorative (aria-hidden); the adjacent text carries the meaning.

import type { ReactNode } from "react"

function Icon({ size = 16, children }: { size?: number; children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

interface IconProps {
  size?: number
}

export const PlaneIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />
  </Icon>
)

export const ArrowRightIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
)

export const ArrowLeftIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M19 12H5M11 18l-6-6 6-6" />
  </Icon>
)

export const SwapIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7" />
  </Icon>
)

export const AlertIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16h.01" />
  </Icon>
)

export const CheckIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="m5 12 5 5 9-10" />
  </Icon>
)

export const InfoIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </Icon>
)

export const SearchIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Icon>
)

export const TicketIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v8a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2z" />
    <path d="M13 6v2M13 11v2M13 16v2" />
  </Icon>
)

export const CardIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 10h18M7 15h3" />
  </Icon>
)

export const MenuIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Icon>
)

export const CloseIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
)

export const MinusIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M5 12h14" />
  </Icon>
)

export const PlusIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)

export const PinIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <path d="M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z" />
    <circle cx="12" cy="9" r="2.5" />
  </Icon>
)

export const UsersIcon = ({ size }: IconProps) => (
  <Icon size={size}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6.5 6.5 0 0 1 3.5 6" />
  </Icon>
)
