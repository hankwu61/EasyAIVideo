import { useState } from 'react'
import { addLibraryAsset, errorMessage } from '../api'
import type { BoundAsset } from '../types'

export default function AssetLibrary({projectId, library, onChange, disabled}: {
  projectId: string; library: BoundAsset[]; onChange: (a: BoundAsset[]) => void; disabled: boolean
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  return <details className="card my-3 p-3 text-sm">
    <summary className="cursor-pointer">共用資產庫 · {library.length} 項</summary>
    <p className="my-2 text-xs text-muted">分集共用系列資產。新增後可在各分鏡綁定；既有綁定保留選取當時的設定。</p>
    <div className="flex flex-wrap gap-2">{library.map(a => <span key={a.id} className="rounded bg-panel-2 px-2 py-1">{{character:'角色',location:'場景',prop:'道具'}[a.kind]}：{a.name}</span>)}</div>
    <form className="mt-3 space-y-2" onSubmit={async e => {
      e.preventDefault(); const form = e.currentTarget; const data = new FormData(form)
      if (!(data.get('file') as File)?.size) data.delete('file')
      setPending(true); setError('')
      try {onChange(await addLibraryAsset(projectId, data)); form.reset()} catch(e) {setError(errorMessage(e))} finally {setPending(false)}
    }}>
      <fieldset disabled={disabled || pending} className="space-y-2">
        <select className="input" name="kind" aria-label="資產類型"><option value="character">角色</option><option value="location">場景</option><option value="prop">道具</option></select>
        <input className="input" name="name" aria-label="資產名稱" placeholder="資產名稱" required maxLength={100} />
        <textarea className="input" name="description" aria-label="外觀描述" placeholder="固定外觀／場景／道具描述（用於圖片生成）" />
        <label className="block text-xs">參考圖（選填）<input className="block mt-1" name="file" type="file" accept="image/*" /></label>
        <button className="btn-primary btn-sm" type="submit">{pending ? '儲存中…' : '新增資產'}</button>
      </fieldset>
      {error && <p role="alert" className="text-danger">{error}</p>}
    </form>
  </details>
}
