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

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model.trim="filters[field.key]" :placeholder="`按${field.label}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, index) in rows"
          :key="String(row.id)"
          :ref="(el) => bindRow(el, index)"
          :class="{ 'row-hit': filtered }"
        >
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
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>
        <template v-if="filtered">命中 {{ total }} 条线路区段记录（当前为筛选结果，「重置条件」可回到全量）</template>
        <template v-else>共 {{ total }} 条线路区段记录</template>
      </span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/section'
const columns = ["区段编码", "区段名称", "所属线路", "起止里程", "管辖工区", "投运日期", "限速值", "区段状态"]
const actions = ["办理投用", "申请限速", "封闭区段"]
const stats = [{"label": "在用区段", "value": 0}, {"label": "限速区段", "value": 0}, {"label": "封闭区段", "value": 0}]

// 筛选输入与后端 query 参数一一对应，避免把中文列名直接拼进 URL 被服务端忽略。
const filterFields = [
  { key: 'keyword', label: '区段编码' },
  { key: 'name', label: '区段名称' },
  { key: 'line', label: '所属线路' },
] as const

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const emptyHint = ref('暂无线路区段数据，可先登记线路区段')
const filters = ref<Record<string, string>>({ keyword: '', name: '', line: '' })
// 最近一次「查询」生效的条件；列表、定位、导出都以它为准。
const appliedQuery = ref('')
const filtered = ref(false)
const rowRefs: HTMLElement[] = []

function bindRow(el: Element | unknown, index: number) {
  if (el instanceof HTMLElement) {
    rowRefs[index] = el
  } else {
    delete rowRefs[index]
  }
}

function buildQuery(): string {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = (filters.value[field.key] ?? '').trim()
    if (value) {
      params.append(field.key, value)
    }
  }
  return params.toString()
}

// 查询条件需要至少填写一项；空白条件不执行筛选，避免给一张全量表或空表造成误解。
function applyFilters() {
  const query = buildQuery()
  if (!query) {
    errorMessage.value = '请先填写筛选条件：区段编码、区段名称、所属线路至少填写一项；如需查看全量请点「重置条件」'
    return
  }
  errorMessage.value = ''
  void load(query, { filtered: true, locate: true })
}

function resetFilters() {
  filters.value = { keyword: '', name: '', line: '' }
  errorMessage.value = ''
  void load('', { filtered: false, locate: false })
}

function describeFilters(query: string): string {
  const labels: Record<string, string> = { keyword: '区段编码', name: '区段名称', line: '所属线路', status: '区段状态' }
  return new URLSearchParams(query)
    .toString()
    .split('&')
    .filter(Boolean)
    .map((pair) => {
      const [key, value] = pair.split('=')
      return `${labels[key] ?? key}「${decodeURIComponent(value ?? '')}」`
    })
    .join('、')
}

async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
  } catch {
    // 响应不是 JSON 时使用兜底说明
  }
  return fallback
}

// 列表与导出共用的取数入口：始终携带最近一次生效的条件，保证三者口径一致。
async function load(query: string, options: { filtered: boolean; locate: boolean }) {
  errorMessage.value = ''
  rowRefs.length = 0
  try {
    const response = await request(`${ENDPOINT}${query ? `?${query}` : ''}`)
    if (!response.ok) {
      throw new Error(await errorDetail(response, '线路区段列表读取失败'))
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    appliedQuery.value = query
    filtered.value = options.filtered && query !== ''
    emptyHint.value = filtered.value
      ? `没有命中符合 ${describeFilters(query)} 的线路区段，请调整条件后重新查询`
      : '暂无线路区段数据，可先登记线路区段'
    if (options.locate && rows.value.length) {
      // 等行渲染完成后定位到第一条命中区段
      requestAnimationFrame(() => rowRefs[0]?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '线路区段列表读取失败'
  }
}

async function exportRows() {
  // 导出严格走最近一次查询生效的条件；输入框改过但没查询，要先说明，不能静默导出旧结果。
  if (buildQuery() !== appliedQuery.value) {
    errorMessage.value = buildQuery()
      ? '筛选条件已修改但尚未查询，请先点「查询」确认筛选结果，再导出'
      : '请先填写筛选条件并点「查询」；如需导出全量清单，请先点「重置条件」'
    return
  }
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/export${appliedQuery.value ? `?${appliedQuery.value}` : ''}`)
    if (!response.ok) {
      throw new Error(await errorDetail(response, '线路区段清单导出失败'))
    }
    const payload = (await response.json()) as { columns?: string[]; items?: Row[]; total?: number }
    const columnsToExport = payload.columns ?? columns
    const items = payload.items ?? []
    if (!items.length) {
      errorMessage.value = filtered.value
        ? `当前筛选（${describeFilters(appliedQuery.value)}）没有命中区段，未生成导出文件`
        : '当前没有可导出的线路区段数据'
      return
    }
    downloadCsv(columnsToExport, items)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '线路区段清单导出失败'
  }
}

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? '' : String(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function downloadCsv(headers: string[], items: Row[]) {
  const lines = [
    headers.map(csvCell).join(','),
    ...items.map((item) => headers.map((header) => csvCell(item[header])).join(',')),
  ]
  // 带 BOM，Excel 直接打开中文不乱码；列序与页面表格、服务端 LIST_FIELDS 完全一致。
  const blob = new Blob([`﻿${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const stamp = new Date().toISOString().slice(0, 10)
  link.href = url
  link.download = `线路区段清单${filtered.value ? '-筛选结果' : '-全量'}-${stamp}.csv`
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
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('线路区段动作未生效，请稍后重试')
    }
    const payload = (await response.json()) as { ok?: boolean; message?: string }
    // 后端用业务结果 ok=false 拦截非法/不可执行的动作，需把原因展示出来
    if (payload.ok === false) {
      throw new Error(payload.message || '线路区段动作未生效')
    }
    // 投用/限速/封闭后按当前条件重新取数，保持列表与服务端同步，定位与筛选照旧
    await load(appliedQuery.value, { filtered: filtered.value, locate: false })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '线路区段操作失败'
  }
}

onMounted(() => load('', { filtered: false, locate: false }))
</script>

<style scoped>
.row-hit {
  background: #eef5ff;
}
.row-hit:first-child {
  box-shadow: inset 3px 0 0 var(--brand);
}
</style>
