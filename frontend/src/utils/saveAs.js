/**
 * 文件保存对话框工具函数
 *
 * 优先使用 File System Access API (showSaveFilePicker)，
 * 让用户选择保存路径和文件名；如果浏览器不支持则回退为传统下载。
 */

/**
 * 弹出"另存为"对话框下载文件
 *
 * @param {Blob} blob - 要保存的文件 Blob
 * @param {Object} options
 * @param {string} options.suggestedName - 建议的文件名（用户可修改），如 'contract_backup_20240601.zip'
 * @param {string} options.mimeType - MIME 类型，如 'application/zip'
 * @param {Array<{description: string, accept: Object}>} [options.types] - 文件类型过滤
 * @returns {Promise<boolean>} - 成功返回 true，用户取消返回 false
 */
export async function saveAsDialog(blob, { suggestedName, mimeType, types }) {
  // 优先使用现代 File System Access API
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName,
        types: types || [
          {
            description: suggestedName.split('.').pop().toUpperCase() + ' 文件',
            accept: { [mimeType]: ['.' + suggestedName.split('.').pop()] },
          },
        ],
      })
      const writable = await handle.createWritable()
      await writable.write(blob)
      await writable.close()
      return true
    } catch (err) {
      // 用户取消选择（AbortError）
      if (err.name === 'AbortError') {
        return false
      }
      // 其他错误，回退传统下载
      console.warn('showSaveFilePicker 失败，回退传统下载:', err)
    }
  }

  // 回退：传统 blob 下载
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = suggestedName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // 延迟释放 URL 确保下载触发
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return true
}

export default saveAsDialog
