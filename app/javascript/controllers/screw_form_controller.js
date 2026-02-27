import { Controller } from "@hotwired/stimulus"

// Syncs screw positions from the 3D placer into hidden form fields.
export default class extends Controller {
  static targets = ["fields", "summary", "submitBtn"]

  connect() {
    this.screws = []
    this._boundHandler = this._onScrewsChanged.bind(this)
    document.addEventListener("screws:changed", this._boundHandler)
  }

  disconnect() {
    document.removeEventListener("screws:changed", this._boundHandler)
  }

  _onScrewsChanged(event) {
    this.screws = event.detail.screws || []
    this._renderFields()
    this._updateSummary()
  }

  _renderFields() {
    if (!this.hasFieldsTarget) return
    let html = ""
    this.screws.forEach((s, i) => {
      const prefix = `screws[${i}]`
      html += `<input type="hidden" name="${prefix}[x]" value="${s.x}">`
      html += `<input type="hidden" name="${prefix}[y]" value="${s.y}">`
      html += `<input type="hidden" name="${prefix}[z]" value="${s.z}">`
      html += `<input type="hidden" name="${prefix}[angle_x]" value="${s.angle_x || 0}">`
      html += `<input type="hidden" name="${prefix}[angle_y]" value="${s.angle_y || 0}">`
      html += `<input type="hidden" name="${prefix}[angle_z]" value="${s.angle_z || 0}">`
    })
    this.fieldsTarget.innerHTML = html
  }

  _updateSummary() {
    if (!this.hasSummaryTarget) return
    const n = this.screws.length
    if (n === 0) {
      this.summaryTarget.textContent = "Sin tornillos colocados"
    } else {
      this.summaryTarget.textContent = `${n} tornillo${n !== 1 ? 's' : ''} colocado${n !== 1 ? 's' : ''}`
    }
  }
}
