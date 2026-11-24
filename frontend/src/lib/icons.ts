/** Inline stroke icons on a 24×24 grid. `circle:cx,cy,r` and `rect:x,y,w,h,rx` are shorthand shapes. */
export const ICONS = {
  plus: ['M12 5v14M5 12h14'],
  chat: ['M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z'],
  path: ['M8.5 6H15a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h6.5', 'circle:6,6,2.5', 'circle:18,18,2.5'],
  library: ['M5 4h4v16H5zM10 4h4v16h-4z', 'm15.5 5 3.8-1 2.7 15.5-3.8 1z'],
  logout: ['M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10'],
  send: ['M12 19V5M6 11l6-6 6 6'],
  arrowRight: ['M5 12h14M13 6l6 6-6 6'],
  arrowLeft: ['M19 12H5M11 18l-6-6 6-6'],
  copy: ['M5 15V5h10', 'rect:9,9,11,11,2'],
  refresh: ['M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7'],
  info: ['circle:12,12,9', 'M12 11v5M12 8h.01'],
  alert: ['M12 4 2.5 20h19L12 4Z', 'M12 10v4M12 17h.01'],
  check: ['m5 12 5 5 9-10'],
  chevron: ['m9 6 6 6-6 6'],
  search: ['circle:11,11,7', 'm20 20-3.5-3.5'],
  trash: ['M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13'],
  menu: ['M4 7h16M4 12h16M4 17h16'],
  close: ['M6 6l12 12M18 6 6 18'],
  external: ['M14 4h6v6M20 4l-9 9', 'M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5'],
  clock: ['circle:12,12,9', 'M12 7v5l3 2'],
  stop: ['rect:7,7,10,10,1.5'],
} as const satisfies Record<string, readonly string[]>

export type IconName = keyof typeof ICONS

export type IconShape =
  | { kind: 'path'; d: string }
  | { kind: 'circle'; cx: number; cy: number; r: number }
  | { kind: 'rect'; x: number; y: number; w: number; h: number; rx: number }

export function iconShapes(name: IconName): IconShape[] {
  return ICONS[name].map((p: string): IconShape => {
    if (p.startsWith('circle:')) {
      const [cx, cy, r] = p.slice(7).split(',').map(Number)
      return { kind: 'circle', cx, cy, r }
    }
    if (p.startsWith('rect:')) {
      const [x, y, w, h, rx] = p.slice(5).split(',').map(Number)
      return { kind: 'rect', x, y, w, h, rx }
    }
    return { kind: 'path', d: p }
  })
}
