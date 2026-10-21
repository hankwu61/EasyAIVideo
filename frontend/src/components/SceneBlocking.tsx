import { useEffect, useState } from 'react'
import type { BoundAsset, Scene, StagePosition } from '../types'
import type { SceneActions } from './SceneCard'

export default function SceneBlocking({ scene, library, disabled, actions }: {
  scene: Scene; library: BoundAsset[]; disabled: boolean; actions: SceneActions
}) {
  const [positions, setPositions] = useState<StagePosition[]>(scene.stage_positions || [])
  const [selected, setSelected] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { setPositions(scene.stage_positions || []) }, [scene.id, scene.stage_positions])
  const locked = disabled || saving
  const dirty = JSON.stringify(positions) !== JSON.stringify(scene.stage_positions || [])
  const characters = [...new Map([...library, ...(scene.asset_bindings || [])].filter(a => a.kind === 'character').map(a => [a.id, a])).values()]
  const current = positions.find(p => p.character_id === selected)
  const change = (patch: Partial<StagePosition>) => setPositions(ps => ps.map(p => p.character_id === selected ? { ...p, ...patch } : p))
  return <section className="space-y-2 rounded border border-border p-3">
    <h4 className="font-semibold">場景俯視圖 · 人物站位</h4>
    <p className="text-muted">先加入角色，再選取標記並點擊圖面安排位置。上方為場景遠端，下方為近端；箭頭表示人物朝向。儲存後會套用至生成提示，鏡頭角度仍由分鏡決定。</p>
    <select aria-label="加入站位角色" className="input" value="" disabled={locked || positions.length >= 30} onChange={e => {
      const a = characters.find(c => c.id === e.target.value)
      if (a) { setPositions(ps => [...ps, {character_id: a.id, name: a.name, x: 50, y: 50, facing: 180}]); setSelected(a.id) }
    }}>
      <option value="">加入角色…</option>
      {characters.filter(a => !positions.some(p => p.character_id === a.id)).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
    </select>
    {!characters.length && <p className="text-muted">請先在角色設定或共用資產庫新增角色。</p>}
    <div className="relative h-64 overflow-hidden rounded border border-border bg-panel-2" aria-label="場景俯視配置圖"
      style={{backgroundImage: 'linear-gradient(to right, #8882 1px, transparent 1px), linear-gradient(to bottom, #8882 1px, transparent 1px)', backgroundSize: '10% 10%'}}
      onClick={e => {
        if (locked || !current) return
        const rect = e.currentTarget.getBoundingClientRect()
        change({x: Math.round(Math.max(0, Math.min(100, (e.clientX - rect.left) / rect.width * 100))), y: Math.round(Math.max(0, Math.min(100, (e.clientY - rect.top) / rect.height * 100)))})
      }}>
      <span className="pointer-events-none absolute inset-x-0 top-1 text-center text-muted">遠端</span>
      <span className="pointer-events-none absolute inset-x-0 bottom-1 text-center text-muted">近端</span>
      {positions.map((p, i) => <button key={p.character_id} type="button" disabled={locked} title={p.name} aria-label={`選取 ${p.name}`}
        className={`absolute flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full border-2 ${selected === p.character_id ? 'border-blue-400 bg-blue-700 text-white' : 'border-border bg-panel'}`}
        style={{left: `clamp(22px, ${p.x}%, calc(100% - 22px))`, top: `clamp(22px, ${p.y}%, calc(100% - 22px))`}}
        onClick={e => {e.stopPropagation(); setSelected(p.character_id)}}>
        <span style={{transform: `rotate(${p.facing}deg)`}}>↑</span><span>{i + 1}</span>
      </button>)}
    </div>
    <div className="flex flex-wrap gap-2">{positions.map((p, i) => <button type="button" key={p.character_id} disabled={locked} className="btn-ghost btn-sm" aria-pressed={selected === p.character_id} onClick={() => setSelected(p.character_id)}>{i + 1}. {p.name}</button>)}</div>
    {current && <div className="flex flex-wrap items-end gap-3">
      {(['x', 'y', 'facing'] as const).map(key => <label key={key}>{ {x: '左右位置 (%)', y: '遠近位置 (%)', facing: '朝向 (°)'}[key] }
        <input type="number" className="input mt-1 w-24" min={0} max={key === 'facing' ? 359 : 100} value={current[key]} disabled={locked}
          onChange={e => {const n = e.target.valueAsNumber; if (Number.isFinite(n)) change({[key]: Math.max(0, Math.min(key === 'facing' ? 359 : 100, n))})}} />
      </label>)}
      <button type="button" className="btn-ghost btn-sm" disabled={locked} onClick={() => {setPositions(ps => ps.filter(p => p.character_id !== selected)); setSelected('')}}>移除站位</button>
    </div>}
    <div className="flex gap-2">
      <button type="button" className="btn-secondary btn-sm" disabled={locked || !dirty} onClick={async () => {
        setSaving(true); setError('')
        try { if (!await actions.patch(scene.id, {stage_positions: positions})) setError('站位儲存失敗，請重試。') }
        catch {setError('站位儲存失敗，請重試。')} finally {setSaving(false)}
      }}>{saving ? '儲存中…' : '儲存站位'}</button>
      <button type="button" className="btn-ghost btn-sm" disabled={locked || !dirty} onClick={() => {setPositions(scene.stage_positions || []); setError('')}}>還原未儲存變更</button>
      {dirty && <span className="text-muted">尚未儲存</span>}
    </div>
    {error && <p role="alert" className="text-danger">{error}</p>}
  </section>
}
