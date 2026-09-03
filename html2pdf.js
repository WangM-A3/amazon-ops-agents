// html2pdf.js — HTML → PDF（playwright-core + 系统 Chrome 无头打印，中文渲染可靠）
// 用法: node html2pdf.js <input.html> <output.pdf>
const { chromium } = require('C:/Users/HZDH/Documents/agent开发/reports/harness_deep_dive/dsh-lab/dsh-home/profiles/web/node_modules/playwright-core')
const fs = require('fs')

async function main() {
  const [htmlPath, pdfPath] = process.argv.slice(2)
  if (!htmlPath || !pdfPath) {
    console.error('usage: node html2pdf.js <in.html> <out.pdf>')
    process.exit(2)
  }
  const html = fs.readFileSync(htmlPath, 'utf-8')
  const executable = fs.existsSync('C:/Program Files (x86)/Google/Chrome/Application/chrome.exe')
    ? 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'
    : 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  const browser = await chromium.launch({ executablePath: executable, headless: true, args: ['--no-sandbox'] })
  try {
    const page = await browser.newPage()
    await page.setContent(html, { waitUntil: 'networkidle' })
    await page.pdf({
      path: pdfPath,
      format: 'A4',
      printBackground: true,
      margin: { top: '16mm', bottom: '18mm', left: '15mm', right: '15mm' },
    })
    console.log('PDF saved:', pdfPath, fs.statSync(pdfPath).size, 'bytes')
  } finally {
    await browser.close()
  }
}

main().catch((e) => { console.error('FAILED:', e.message); process.exit(1) })
