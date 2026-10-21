import type { Project } from '../types'

export function generateVideoPromptsText(project: Project): string {
  const lines: string[] = [
    `【專案】${project.title || project.id} - 影片提示詞`,
    `【總場景數】${project.scenes.length} 場`,
    '',
  ]
  project.scenes.forEach((scene, i) => {
    lines.push('='.repeat(50))
    lines.push(`第 ${i + 1} 場 (Scene ${i + 1}):`)
    const prompt = (scene.video_prompt ?? '').trim()
    lines.push(prompt || '(無影片提示詞)')
    lines.push('')
  })
  return lines.join('\n').trim() + '\n'
}

export function generateImagePromptsText(project: Project): string {
  const lines: string[] = [
    `【專案】${project.title || project.id} - 圖片提示詞`,
    `【總場景數】${project.scenes.length} 場`,
    '',
  ]
  project.scenes.forEach((scene, i) => {
    lines.push('='.repeat(50))
    lines.push(`第 ${i + 1} 場 (Scene ${i + 1}):`)
    const prompt = (scene.image_prompt ?? '').trim()
    lines.push(prompt || '(無圖片提示詞)')
    lines.push('')
  })
  return lines.join('\n').trim() + '\n'
}

export function generateNarrationText(project: Project): string {
  const lines: string[] = [
    `【專案】${project.title || project.id} - 旁白台詞`,
    `【總場景數】${project.scenes.length} 場`,
    '',
  ]
  project.scenes.forEach((scene, i) => {
    lines.push('='.repeat(50))
    lines.push(`第 ${i + 1} 場 (Scene ${i + 1}):`)
    if (scene.lines && scene.lines.length > 0) {
      const dialogues = scene.lines.map((l) => `${l.speaker ? `${l.speaker}: ` : ''}${l.text.trim()}`)
      lines.push(dialogues.join('\n'))
    } else {
      const text = (scene.narration ?? '').trim()
      lines.push(text || '(無旁白台詞)')
    }
    lines.push('')
  })
  return lines.join('\n').trim() + '\n'
}

export function generateFullScriptText(project: Project): string {
  const lines: string[] = [
    `【專案名稱】${project.title || project.id}`,
    `【總場景數】${project.scenes.length} 場`,
    `【影片比例】${project.aspect_ratio}`,
    '',
  ]
  project.scenes.forEach((scene, i) => {
    lines.push('='.repeat(50))
    lines.push(`【第 ${i + 1} 場 (Scene ${i + 1})】`)
    lines.push('')
    lines.push('【旁白 / 台詞】')
    if (scene.lines && scene.lines.length > 0) {
      const dialogues = scene.lines.map((l) => `${l.speaker ? `${l.speaker}: ` : ''}${l.text.trim()}`)
      lines.push(dialogues.join('\n'))
    } else {
      const text = (scene.narration ?? '').trim()
      lines.push(text || '(無旁白台詞)')
    }
    lines.push('')
    lines.push('【圖片提示詞】')
    const ip = (scene.image_prompt ?? '').trim()
    lines.push(ip || '(無圖片提示詞)')
    lines.push('')
    lines.push('【影片提示詞】')
    const vp = (scene.video_prompt ?? '').trim()
    lines.push(vp || '(無影片提示詞)')
    lines.push('')
  })
  return lines.join('\n').trim() + '\n'
}

export function downloadTextBlob(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export type TextExportKind = 'video_prompts' | 'image_prompts' | 'narration' | 'script'

export function downloadProjectText(project: Project, kind: TextExportKind) {
  const baseTitle = (project.title || project.id).replace(/[\\/:*?"<>|\r\n]+/g, '_').trim() || 'project'
  switch (kind) {
    case 'video_prompts':
      downloadTextBlob(`${baseTitle}_影片提示詞.txt`, generateVideoPromptsText(project))
      break
    case 'image_prompts':
      downloadTextBlob(`${baseTitle}_圖片提示詞.txt`, generateImagePromptsText(project))
      break
    case 'narration':
      downloadTextBlob(`${baseTitle}_旁白.txt`, generateNarrationText(project))
      break
    case 'script':
      downloadTextBlob(`${baseTitle}_完整腳本提示詞.txt`, generateFullScriptText(project))
      break
  }
}
