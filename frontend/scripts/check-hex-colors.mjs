import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const targets = ['src', 'tailwind.config.ts']
const ignoredFiles = new Set([
  path.normalize('src/pages/AgentConfigPage.tsx'),
  path.normalize('src/pages/CompliancePage.tsx'),
])
const sourceExtensions = new Set(['.ts', '.tsx', '.css'])
const hexPattern = /#[0-9a-fA-F]{3,8}\b/g

function walk(entry) {
  const absolute = path.join(root, entry)
  if (!fs.existsSync(absolute)) return []

  const stat = fs.statSync(absolute)
  if (stat.isFile()) return [absolute]

  const files = []
  for (const child of fs.readdirSync(absolute)) {
    if (child === 'node_modules' || child === 'dist') continue
    files.push(...walk(path.join(entry, child)))
  }
  return files
}

function stripComments(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
}

const violations = []

for (const file of targets.flatMap(walk)) {
  const relative = path.relative(root, file)
  if (ignoredFiles.has(path.normalize(relative))) continue
  if (!sourceExtensions.has(path.extname(file))) continue

  const source = stripComments(fs.readFileSync(file, 'utf8'))
  const lines = source.split(/\r?\n/)
  lines.forEach((line, index) => {
    const matches = line.match(hexPattern)
    if (!matches) return
    violations.push({
      file: relative,
      line: index + 1,
      values: Array.from(new Set(matches)),
    })
  })
}

if (violations.length > 0) {
  console.error('Raw hex colors found. Use design tokens or Tailwind semantic classes instead.')
  for (const violation of violations) {
    console.error(`${violation.file}:${violation.line} ${violation.values.join(', ')}`)
  }
  process.exit(1)
}

console.log('No raw hex colors found in checked source files.')
