import { useState } from 'react'
import { CheckCircle2, PlugZap, XCircle } from 'lucide-react'
import { errorMessage, testConfig } from '../../api'
import { useLang } from '../../i18n'
import type { ConfigTestKind, ConfigTestResult } from '../../types'
import { cx } from '../../utils'
import { Spinner } from '../ui'

export default function TestButton({
  kind,
  beforeTest,
  disabled,
}: {
  kind: ConfigTestKind
  /** Runs before the test (e.g. saving unsaved changes). Return false to abort. */
  beforeTest?: () => Promise<boolean>
  disabled?: boolean
}) {
  const { t } = useLang()
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<ConfigTestResult | null>(null)

  const run = async () => {
    setTesting(true)
    setResult(null)
    try {
      if (beforeTest && !(await beforeTest())) return
      setResult(await testConfig(kind))
    } catch (e) {
      setResult({ ok: false, message: errorMessage(e), elapsed_ms: 0 })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="btn-secondary btn-sm" onClick={() => void run()} disabled={testing || disabled}>
        {testing ? <Spinner size={13} /> : <PlugZap size={13} />}
        {testing ? t('testing') : t('test_connection')}
      </button>
      {result && (
        <span
          className={cx(
            'inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-xs animate-fade-in',
            result.ok ? 'border-success/30 bg-success/10 text-success' : 'border-danger/30 bg-danger/10 text-danger',
          )}
        >
          {result.ok ? <CheckCircle2 size={13} className="shrink-0" /> : <XCircle size={13} className="shrink-0" />}
          <span className="truncate">
            {result.ok ? t('test_ok') : t('test_fail')}
            {result.message ? ` · ${result.message}` : ''}
          </span>
          {result.elapsed_ms > 0 && <span className="shrink-0 opacity-70 tabular-nums">{result.elapsed_ms} ms</span>}
        </span>
      )}
    </div>
  )
}
