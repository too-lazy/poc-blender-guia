import { Controller } from "@hotwired/stimulus"

// Lightbox controller for viewing Blender render images full-size.
// Usage: <div data-controller="lightbox">
//          <img src="..." data-action="click->lightbox#open" data-lightbox-src-value="full-size-url">
//        </div>
export default class extends Controller {
  static values = { src: String }

  open(event) {
    const src = event.currentTarget.dataset.lightboxSrcValue || event.currentTarget.src

    const overlay = document.createElement("div")
    overlay.id = "lightbox-overlay"
    overlay.style.cssText = `
      position: fixed; inset: 0; z-index: 9999;
      background: rgba(0,0,0,0.85);
      display: flex; align-items: center; justify-content: center;
      flex-direction: column; gap: 16px;
      cursor: pointer;
    `

    const img = document.createElement("img")
    img.src = src
    img.style.cssText = `
      max-width: 90vw; max-height: 80vh;
      border: 3px solid white;
      box-shadow: 6px 6px 0px 0px rgba(255,255,255,0.3);
    `

    const controls = document.createElement("div")
    controls.style.cssText = "display: flex; gap: 12px; align-items: center;"

    const downloadBtn = document.createElement("a")
    downloadBtn.href = src
    downloadBtn.download = "render.png"
    downloadBtn.textContent = "⬇ Download"
    downloadBtn.style.cssText = `
      padding: 10px 20px; background: #14B8A6; color: black;
      font-weight: bold; font-size: 14px; border: 2px solid black;
      box-shadow: 3px 3px 0px 0px black; text-decoration: none;
    `
    downloadBtn.addEventListener("click", (e) => e.stopPropagation())

    const closeBtn = document.createElement("button")
    closeBtn.textContent = "✕ Close"
    closeBtn.style.cssText = `
      padding: 10px 20px; background: white; color: black;
      font-weight: bold; font-size: 14px; border: 2px solid black;
      box-shadow: 3px 3px 0px 0px black; cursor: pointer;
    `

    controls.appendChild(downloadBtn)
    controls.appendChild(closeBtn)
    overlay.appendChild(img)
    overlay.appendChild(controls)

    const close = () => overlay.remove()
    overlay.addEventListener("click", close)
    closeBtn.addEventListener("click", close)
    img.addEventListener("click", (e) => e.stopPropagation())

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close()
    }, { once: true })

    document.body.appendChild(overlay)
  }
}
