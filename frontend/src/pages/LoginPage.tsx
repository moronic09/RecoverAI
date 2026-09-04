import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Zap } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'

export default function LoginPage() {
  const navigate = useNavigate()
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('demo@recoverai.com')
  const [password, setPassword] = useState('demo1234')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = isRegister
        ? await api.register(email, password, name)
        : await api.login(email, password)
      localStorage.setItem('token', res.access_token)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md"
      >
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="border border-ink p-2">
              <Zap className="w-8 h-8 text-ink" />
            </div>
            <h1 className="text-3xl font-bold font-serif text-ink">
              RecoverAI
            </h1>
          </div>
          <p className="text-slate-500">Payment recovery intelligence for Razorpay merchants</p>
        </div>

        <div className="border border-paper-line bg-[#EFEBE2] p-8">
          <h2 className="text-xl font-semibold text-ink mb-6">{isRegister ? 'Create account' : 'Sign in'}</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <div>
                  <label className="block text-sm text-slate-500 mb-1">Business name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-2.5 bg-paper border-b border-paper-line focus:border-ink focus:outline-none transition"
                  required
                />
              </div>
            )}
            <div>
                <label className="block text-sm text-slate-500 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 bg-paper border-b border-paper-line focus:border-ink focus:outline-none transition"
                required
              />
            </div>
            <div>
                <label className="block text-sm text-slate-500 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-paper border-b border-paper-line focus:border-ink focus:outline-none transition"
                required
              />
            </div>

            {error && (
              <p className="text-flatline text-sm border-l-2 border-flatline px-3 py-2">{error}</p>
            )}

            <Button type="submit" className="w-full" loading={loading}>
              {isRegister ? 'Create account' : 'Sign in'}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button
              type="button"
              onClick={() => setIsRegister(!isRegister)}
              className="text-revival hover:text-ink font-medium"
            >
              {isRegister ? 'Sign in' : 'Register'}
            </button>
          </p>

          {!isRegister && (
            <p className="mt-4 text-center text-xs text-slate-500">
              Demo: demo@recoverai.com / demo1234
            </p>
          )}
        </div>
      </motion.div>
    </div>
  )
}
