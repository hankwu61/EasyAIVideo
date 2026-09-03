import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cx } from '../utils'

interface MenuProps {
  trigger: (props: { open: boolean; onClick: () => void }) => ReactNode
  children: (close: () => void) => ReactNode
  className?: string
}

/** Small click-to-open dropdown that closes on outside click / Escape. */
export default function Menu({ trigger, children, className }: MenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} className={cx('relative', className)}>
      {trigger({ open, onClick: () => setOpen((o) => !o) })}
      {open && <div className="menu animate-fade-in">{children(() => setOpen(false))}</div>}
    </div>
  )
}
