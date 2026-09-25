<template>
  <section class="page" data-module="section">
    <header class="page-head">
      <div>
        <h2>线路区段管理</h2>
        <p class="page-desc">维护线路区段，围绕区段编码、区段名称、所属线路、起止里程做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记线路区段</button>
        <button class="btn" type="button" @click="exportRows">导出线路区段清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applySearch">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p v-if="isFiltered" class="filter-hint">
      当前筛选条件：{{ activeFilterText }}，命中 {{ total }} 条；导出内容与下表一致。
      <button class="link" type="button" @click="resetFilters">清除条件回到全量</button>
    </p>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :id="`section-row-${row.id}`" :class="{ 'row-hit': hitRowId === Number(row.id) }">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length && !errorMessage">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>{{ isFiltered ? `筛选命中 ${total} 条线路区段记录` : `共 ${total} 条线路区段记录` }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/section'
const columns = ["区段编码", "区段名称", "所属线路", "起止里程", "管辖工区", "投运日期", "限速值", "区段状态"]
const actions = ["办理投用", "申请限速", "封闭区段"]
const statuses = ["在建", "已投用", "限速运行", "已封闭"]
const stats = [{"label": "在用区段", "value": 0}, {"label": "限速区段", "value": 0}, {"label": "封闭区段", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
// filters 是输入框草稿，appliedFilters 是最近一次「查询」生效的条件；列表与导出都以它为准
const filters = ref<Record<string, string>>({})
const appliedFilters = ref<Record<string, string>>({})
const hitRowId = ref(-1)
const filterFields = columns.slice(0, 3)

const isFiltered = computed(() => Object.values(appliedFilters.value).some((value) => value.trim()))
const activeFilterText = computed(() =>
  filterFields
    .filter((field) => appliedFilters.value[field]?.trim())
    .map((field) => `${field}「${appliedFilters.value[field].trim()}」`)
    .join('、'),
)
const emptyHint = computed(() =>
  isFiltered.value
    ? `没有符合条件（${activeFilterText.value}）的线路区段，不是没有数据；请调整条件后重新查询，或点「重置条件」查看全量。`
    : '暂无线路区段数据，可先登记线路区段',
)

/** 把生效条件拼成查询串，列表接口与导出接口共用，保证两边取数口径一致。 */
function toQuery(conditions: Record<string, string>): string {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = (conditions[field] ?? '').trim()
    if (value) {
      params.append(field, value)
    }
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

function applySearch() {
  const trimmed: Record<string, string> = {}
  for (const field of filterFields) {
    trimmed[field] = (filters.value[field] ?? '').trim()
  }
  // 条件不完整（一个有效条件都没有）时说明原因，保留原列表，不拿空表误导成“没数据”
  if (!Object.values(trimmed).some(Boolean)) {
    errorMessage.value = '请至少填写一个查询条件（区段编码、区段名称或所属线路）后再查询；不设条件请点「重置条件」查看全量。'
    return
  }
  filters.value = trimmed
  appliedFilters.value = trimmed
  void reload()
}

function resetFilters() {
  filters.value = {}
  appliedFilters.value = {}
  errorMessage.value = ''
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    // 导出走当前已生效的筛选条件，和列表、服务端取数完全同源
    const response = await request(`${ENDPOINT}/export${toQuery(appliedFilters.value)}`)
    if (!response.ok) {
      throw new Error(`导出请求被拒绝（${response.status}），请稍后重试`)
    }
    const payload = await response.json()
    const exportColumns: string[] = Array.isArray(payload.columns) ? payload.columns : columns
    const items: Row[] = payload.items ?? []
    if (!items.length) {
      errorMessage.value = isFiltered.value
        ? `当前条件（${activeFilterText.value}）没有命中任何区段，暂无可导出内容；请调整条件或重置后再导出。`
        : '当前没有可导出的线路区段数据。'
      return
    }
    downloadCsv(exportColumns, items)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '线路区段清单导出失败'
  }
}

function downloadCsv(exportColumns: string[], items: Row[]) {
  const escape = (value: unknown) => {
    const text = value === null || value === undefined ? '' : String(value)
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  const lines = [
    exportColumns.map(escape).join(','),
    ...items.map((row) => exportColumns.map((column) => escape(row[column])).join(',')),
  ]
  // 加 BOM，避免 Excel 打开中文乱码；列序严格按服务端返回的 columns，行序与列表一致
  const blob = new Blob([`\uFEFF${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  link.href = url
  link.download = `线路区段清单_${stamp}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function openCreate() {
  errorMessage.value = '线路区段登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('线路区段动作未生效，请稍后重试')
    }
    // 投用/限速/封闭后按当前条件重新取数，保持列表与服务端同步
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '线路区段操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  hitRowId.value = -1
  try {
    const response = await request(`${ENDPOINT}${toQuery(appliedFilters.value)}`)
    if (!response.ok) {
      throw new Error('线路区段列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (isFiltered.value && rows.value.length) {
      // 查询后定位并高亮第一条命中行
      await nextTick()
      const firstId = Number(rows.value[0].id)
      hitRowId.value = firstId
      document.getElementById(`section-row-${firstId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      window.setTimeout(() => {
        if (hitRowId.value === firstId) {
          hitRowId.value = -1
        }
      }, 2000)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '线路区段列表读取失败'
  }
}

onMounted(reload)
</script>
