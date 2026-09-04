import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(amount)
}

export function formatPercent(value: number) {
  return `${value.toFixed(1)}%`
}

export function formatReason(reason: string) {
  return reason.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
