import { useEffect, useState } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'

interface CountUpProps {
  value: number
  prefix?: string
  suffix?: string
  decimals?: number
  duration?: number
}

export function CountUp({ value, prefix = '', suffix = '', decimals = 0, duration = 1.2 }: CountUpProps) {
  const spring = useSpring(0, { duration: duration * 1000 })
  const display = useTransform(spring, (v) => `${prefix}${v.toFixed(decimals)}${suffix}`)
  const [text, setText] = useState(`${prefix}0${suffix}`)

  useEffect(() => {
    spring.set(value)
    return display.on('change', (v) => setText(v))
  }, [value, spring, display, prefix, suffix, decimals])

  return <motion.span>{text}</motion.span>
}

export function FadeIn({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      {children}
    </motion.div>
  )
}
