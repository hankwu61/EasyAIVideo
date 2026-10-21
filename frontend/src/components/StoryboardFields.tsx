import SceneBlocking from './SceneBlocking'
import { useState } from 'react'
import type { BoundAsset, Scene } from '../types'
import type { SceneActions } from './SceneCard'

export default function StoryboardFields({scene, library, groups, disabled, actions}: {
  scene: Scene; library: BoundAsset[]; groups: string[]; disabled: boolean; actions: SceneActions
}) {
  const [pending, setPending] = useState(false)
  const locked = disabled || pending
  const bindings = scene.asset_bindings || []
  const update = async (ids: string[]) => {
    setPending(true)
    try { await actions.patch(scene.id, {asset_ids: ids}) } finally { setPending(false) }
  }
  return <details className="rounded-lg border border-border p-2 text-xs">
    <summary className="cursor-pointer">{scene.group || '未分組'} · 俯視站位 {scene.stage_positions?.length || 0} · 綁定資產 {bindings.length} · 歷史版本 {scene.media_history?.length || 0}</summary>
    <div className="mt-3 space-y-3">
      <label className="block">分鏡群組（同名歸為一組，播放順序不變）
        <input key={scene.group} aria-label="分鏡群組" className="input mt-1" list={`groups-${scene.id}`} defaultValue={scene.group || ''} maxLength={100} disabled={locked}
          onBlur={e => { if (e.target.value.trim() !== (scene.group || '')) void actions.patch(scene.id, {group: e.target.value.trim()}) }} />
        <datalist id={`groups-${scene.id}`}>{groups.map(g => <option key={g} value={g} />)}</datalist>
      </label>
      <p className="text-muted">選取資產會保存當時的外觀描述與參考圖，並將現有畫面標記為待更新。</p>
      <div className="flex flex-wrap gap-2">
        {library.map(a => <label key={a.id} className="flex items-center gap-1 rounded border border-border p-2">
          <input type="checkbox" disabled={locked} checked={bindings.some(b => b.id === a.id)} onChange={e => void update(e.target.checked ? [...bindings.map(b => b.id), a.id] : bindings.filter(b => b.id !== a.id).map(b => b.id))} />
          {a.image_url && <img src={a.image_url} alt="" className="h-8 w-8 rounded object-cover" />}
          {{character:'角色',location:'場景',prop:'道具'}[a.kind]}：{a.name}
        </label>)}
        {!library.length && <span className="text-muted">請先在上方共用資產庫新增資產。</span>}
      </div>
      {bindings.some(b => !library.some(a => a.id === b.id)) && <button disabled={locked} className="btn-ghost btn-sm" onClick={() => void update(bindings.filter(b => library.some(a => a.id === b.id)).map(b => b.id))}>移除已不存在的資產綁定</button>}
      <SceneBlocking scene={scene} library={library} disabled={locked} actions={actions} />
      <div className="flex gap-2 overflow-x-auto">
        {(scene.media_history || []).map((v, i) => {
          const current = scene[`${v.kind}_url`] === v.url
          return <div key={v.id} className="w-32 shrink-0 rounded border border-border p-2">
            {v.kind === 'video' ? <video src={v.url} controls preload="none" className="h-20 w-full" /> : <a href={v.url} target="_blank" rel="noreferrer"><img src={v.url} alt={`版本 ${i+1}`} className="h-20 w-full object-contain" /></a>}
            <p>{{image:'首幀',end_image:'尾幀',video:'影片'}[v.kind]} · 版本 {i+1}</p>
            <p className="text-muted">{new Date(v.created_at).toLocaleString()}</p>
            <button className="btn-ghost btn-sm" disabled={locked || current} onClick={async () => {setPending(true); try {await actions.selectVersion(scene.id, v.id)} finally {setPending(false)}}}>{current ? '使用中' : '使用此版本'}</button>
          </div>
        })}
      </div>
    </div>
  </details>
}
