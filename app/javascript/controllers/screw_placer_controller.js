import { Controller } from "@hotwired/stimulus"

// Interactive screw placement on 3D dental model.
// Click on mesh surface to place screw markers with raycasting.
export default class extends Controller {
  static values = { upperUrl: String, lowerUrl: String, existing: { type: Array, default: [] } }
  static targets = ["container", "counter", "screwTable"]

  async connect() {
    this.screws = []
    this.markers = []
    this.isDragging = false
    this.selectedIndex = -1

    this.showLoading()
    try {
      await this.loadThreeJS()
      this.initScene()
      await this.loadModels()
      this.loadExistingScrews()
      this.hideLoading()
      this.animate()
    } catch (e) {
      console.error("Screw Placer error:", e)
      this.hideLoading()
      this.containerTarget.innerHTML = `<div style="padding:40px;text-align:center;color:#991b1b;font-weight:bold">⚠ ${e.message}</div>`
    }
  }

  disconnect() {
    if (this.animationId) cancelAnimationFrame(this.animationId)
    if (this.meshTargets) {
      this.meshTargets.forEach(m => { m.geometry?.dispose(); m.material?.dispose() })
    }
    if (this.markers) {
      this.markers.forEach(g => {
        g.traverse(child => { child.geometry?.dispose(); child.material?.dispose() })
      })
    }
    if (this.renderer) { this.renderer.dispose(); this.renderer.domElement.remove() }
    if (this._onResize) window.removeEventListener("resize", this._onResize)
  }

  showLoading() {
    this.loadingEl = document.createElement("div")
    this.loadingEl.style.cssText = "display:flex;align-items:center;justify-content:center;width:100%;height:100%;background:#FFFBF5;"
    this.loadingEl.innerHTML = `<div style="text-align:center"><div style="font-size:24px;margin-bottom:8px">🔩</div><div style="font-weight:800;font-size:14px;color:#6366F1">Cargando modelo…</div></div>`
    this.containerTarget.appendChild(this.loadingEl)
  }

  hideLoading() { if (this.loadingEl) this.loadingEl.remove() }

  async loadThreeJS() {
    if (this.THREE) return
    const CDN = "https://esm.sh/three@0.170.0"
    const [three, controls, stlLoader] = await Promise.all([
      import(CDN),
      import(`${CDN}/examples/jsm/controls/OrbitControls.js`),
      import(`${CDN}/examples/jsm/loaders/STLLoader.js`)
    ])
    this.THREE = three
    this.OrbitControls = controls.OrbitControls
    this.STLLoader = stlLoader.STLLoader
  }

  initScene() {
    const THREE = this.THREE
    const w = this.containerTarget.clientWidth
    const h = this.containerTarget.clientHeight || 600

    this.scene = new THREE.Scene()
    this.scene.background = new THREE.Color(0xFFFBF5)
    this.camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 1000)
    this.camera.position.set(0, 0, 100)

    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setSize(w, h)
    this.renderer.setPixelRatio(window.devicePixelRatio)
    this.containerTarget.appendChild(this.renderer.domElement)

    this.controls = new this.OrbitControls(this.camera, this.renderer.domElement)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.08

    // Lighting
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const dir = new THREE.DirectionalLight(0xffffff, 1.0)
    dir.position.set(50, 80, 50)
    this.scene.add(dir)
    const fill = new THREE.DirectionalLight(0xffffff, 0.4)
    fill.position.set(-30, -20, 40)
    this.scene.add(fill)

    // Raycaster
    this.raycaster = new THREE.Raycaster()
    this.mouse = new THREE.Vector2()
    this.meshTargets = []

    // Track drag vs click
    this.renderer.domElement.addEventListener("pointerdown", (e) => { this.isDragging = false; this._downPos = { x: e.clientX, y: e.clientY } })
    this.renderer.domElement.addEventListener("pointermove", (e) => {
      if (this._downPos) {
        const dx = e.clientX - this._downPos.x, dy = e.clientY - this._downPos.y
        if (Math.sqrt(dx*dx + dy*dy) > 5) this.isDragging = true
      }
    })
    this.renderer.domElement.addEventListener("pointerup", (e) => {
      if (!this.isDragging && e.button === 0) this._onClick(e)
      this._downPos = null
    })

    this._onResize = () => {
      const w = this.containerTarget.clientWidth, h = this.containerTarget.clientHeight || 600
      this.camera.aspect = w / h
      this.camera.updateProjectionMatrix()
      this.renderer.setSize(w, h)
    }
    window.addEventListener("resize", this._onResize)
  }

  async loadModels() {
    const THREE = this.THREE
    const loader = new this.STLLoader()
    const material = new THREE.MeshPhysicalMaterial({ color: 0xE6D9BF, roughness: 0.4, clearcoat: 0.1 })

    const urls = [this.upperUrlValue]
    if (this.hasLowerUrlValue && this.lowerUrlValue) urls.push(this.lowerUrlValue)

    for (const url of urls) {
      const resp = await fetch(url, { cache: 'no-store' })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const buf = await resp.arrayBuffer()
      const geo = loader.parse(buf)
      const mesh = new THREE.Mesh(geo, material.clone())
      this.scene.add(mesh)
      this.meshTargets.push(mesh)
    }

    // Center all meshes
    const box = new THREE.Box3()
    this.meshTargets.forEach(m => box.expandByObject(m))
    const center = new THREE.Vector3()
    box.getCenter(center)
    this.meshTargets.forEach(m => m.position.sub(center))
    this._meshOffset = center.clone()

    // Store model size for camera presets
    const size = new THREE.Vector3()
    box.getSize(size)
    this._modelMaxDim = Math.max(size.x, size.y, size.z)

    this._fitCamera()
  }

  _fitCamera() {
    const fov = this.camera.fov * (Math.PI / 180)
    const dist = this._modelMaxDim / (2 * Math.tan(fov / 2)) * 1.5
    this.camera.position.set(dist * 0.5, dist * 0.5, dist)
    this.camera.lookAt(0, 0, 0)
    this.controls.target.set(0, 0, 0)
    this.controls.update()
  }

  loadExistingScrews() {
    if (!this.existingValue || this.existingValue.length === 0) return
    for (const pos of this.existingValue) {
      const adjusted = {
        x: pos.x - this._meshOffset.x,
        y: pos.y - this._meshOffset.y,
        z: pos.z - this._meshOffset.z
      }
      this._addMarker(adjusted, pos)
    }
    this._updateUI()
  }

  // --- Camera presets ---

  viewTop() {
    const d = this._modelMaxDim * 1.2
    this.camera.position.set(0, d, 0)
    this.camera.lookAt(0, 0, 0)
    this.controls.target.set(0, 0, 0)
    this.controls.update()
  }

  viewFront() {
    const d = this._modelMaxDim * 1.2
    this.camera.position.set(0, 0, d)
    this.camera.lookAt(0, 0, 0)
    this.controls.target.set(0, 0, 0)
    this.controls.update()
  }

  viewRight() {
    const d = this._modelMaxDim * 1.2
    this.camera.position.set(d, 0, 0)
    this.camera.lookAt(0, 0, 0)
    this.controls.target.set(0, 0, 0)
    this.controls.update()
  }

  zoomFit() { this._fitCamera() }

  zoomIn() {
    this.camera.position.multiplyScalar(0.75)
    this.controls.update()
  }

  zoomOut() {
    this.camera.position.multiplyScalar(1.33)
    this.controls.update()
  }

  // --- Screw placement ---

  _onClick(event) {
    const THREE = this.THREE
    const rect = this.renderer.domElement.getBoundingClientRect()
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

    this.raycaster.setFromCamera(this.mouse, this.camera)
    const intersects = this.raycaster.intersectObjects(this.meshTargets)

    if (intersects.length > 0) {
      const point = intersects[0].point
      const worldPos = {
        x: point.x + this._meshOffset.x,
        y: point.y + this._meshOffset.y,
        z: point.z + this._meshOffset.z
      }
      this._addMarker(point, worldPos)
      this._updateUI()
      this._syncFormFields()
    }
  }

  _addMarker(displayPos, worldPos) {
    const THREE = this.THREE
    const group = new THREE.Group()

    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.8, 16, 16),
      new THREE.MeshPhysicalMaterial({ color: 0xEF4444, emissive: 0xEF4444, emissiveIntensity: 0.3 })
    )
    group.add(sphere)

    const cyl = new THREE.Mesh(
      new THREE.CylinderGeometry(0.3, 0.3, 4, 12),
      new THREE.MeshPhysicalMaterial({ color: 0x3B82F6, emissive: 0x3B82F6, emissiveIntensity: 0.2 })
    )
    cyl.position.y = 2.5
    group.add(cyl)

    group.position.copy(new THREE.Vector3(displayPos.x, displayPos.y, displayPos.z))
    this.scene.add(group)
    this.markers.push(group)
    this.screws.push({ x: worldPos.x, y: worldPos.y, z: worldPos.z, angle_x: 0, angle_y: 0, angle_z: 0 })
  }

  _updateUI() {
    const n = this.screws.length
    if (this.hasCounterTarget) {
      this.counterTarget.textContent = `${n} tornillo${n !== 1 ? 's' : ''}`
    }
    this._renderTable()
    this.dispatch("updated", { detail: { screws: this.screws } })
  }

  _renderTable() {
    if (!this.hasScrewTableTarget) return
    if (this.screws.length === 0) {
      this.screwTableTarget.innerHTML = `<p class="text-sm text-slate-400 italic py-4 text-center">Haz click en el modelo para colocar tornillos</p>`
      return
    }
    let html = `<table class="w-full text-xs"><thead><tr class="text-slate-500 border-b border-sky-100">
      <th class="py-2 px-1 text-left font-semibold">#</th>
      <th class="py-2 px-1 text-center font-semibold">X (mm)</th>
      <th class="py-2 px-1 text-center font-semibold">Y (mm)</th>
      <th class="py-2 px-1 text-center font-semibold">Z (mm)</th>
      <th class="py-2 px-1 text-center font-semibold">Áng X°</th>
      <th class="py-2 px-1 text-center font-semibold">Áng Y°</th>
      <th class="py-2 px-1 text-center font-semibold">Áng Z°</th>
      <th class="py-2 px-1"></th>
    </tr></thead><tbody>`
    this.screws.forEach((s, i) => {
      html += `<tr class="border-b border-sky-50 hover:bg-sky-50/30 ${this.selectedIndex === i ? 'bg-amber-50' : ''}">
        <td class="py-1.5 px-1 font-semibold text-slate-600">${i + 1}</td>
        <td class="py-1.5 px-1"><input type="number" step="0.01" value="${s.x.toFixed(2)}" data-index="${i}" data-field="x" data-action="change->screw-placer#updateCoord" class="w-full text-center bg-transparent border border-slate-200 rounded px-1 py-0.5 focus:border-sky-400 focus:outline-none"></td>
        <td class="py-1.5 px-1"><input type="number" step="0.01" value="${s.y.toFixed(2)}" data-index="${i}" data-field="y" data-action="change->screw-placer#updateCoord" class="w-full text-center bg-transparent border border-slate-200 rounded px-1 py-0.5 focus:border-sky-400 focus:outline-none"></td>
        <td class="py-1.5 px-1"><input type="number" step="0.01" value="${s.z.toFixed(2)}" data-index="${i}" data-field="z" data-action="change->screw-placer#updateCoord" class="w-full text-center bg-transparent border border-slate-200 rounded px-1 py-0.5 focus:border-sky-400 focus:outline-none"></td>
        <td class="py-1.5 px-1"><input type="number" step="1" value="${s.angle_x.toFixed(0)}" data-index="${i}" data-field="angle_x" data-action="change->screw-placer#updateCoord" class="w-full text-center bg-transparent border border-slate-200 rounded px-1 py-0.5 focus:border-sky-400 focus:outline-none"></td>
        <td class="py-1.5 px-1"><input type="number" step="1" value="${s.angle_y.toFixed(0)}" data-index="${i}" data-field="angle_y" data-action="change->screw-placer#updateCoord" class="w-full text-center bg-transparent border border-slate-200 rounded px-1 py-0.5 focus:border-sky-400 focus:outline-none"></td>
        <td class="py-1.5 px-1"><input type="number" step="1" value="${s.angle_z.toFixed(0)}" data-index="${i}" data-field="angle_z" data-action="change->screw-placer#updateCoord" class="w-full text-center bg-transparent border border-slate-200 rounded px-1 py-0.5 focus:border-sky-400 focus:outline-none"></td>
        <td class="py-1.5 px-1"><button data-action="click->screw-placer#removeAt" data-index="${i}" class="text-red-400 hover:text-red-600 font-bold" title="Eliminar">✕</button></td>
      </tr>`
    })
    html += '</tbody></table>'
    this.screwTableTarget.innerHTML = html
  }

  updateCoord(event) {
    const i = parseInt(event.target.dataset.index)
    const field = event.target.dataset.field
    const val = parseFloat(event.target.value) || 0
    if (i < 0 || i >= this.screws.length) return

    this.screws[i][field] = val

    // Update 3D marker position if coordinate changed
    if (['x', 'y', 'z'].includes(field)) {
      const s = this.screws[i]
      this.markers[i].position.set(
        s.x - this._meshOffset.x,
        s.y - this._meshOffset.y,
        s.z - this._meshOffset.z
      )
    }
    this._syncFormFields()
  }

  removeAt(event) {
    const i = parseInt(event.currentTarget.dataset.index)
    if (i < 0 || i >= this.screws.length) return
    const marker = this.markers.splice(i, 1)[0]
    marker.traverse(child => { child.geometry?.dispose(); child.material?.dispose() })
    this.scene.remove(marker)
    this.screws.splice(i, 1)
    if (this.selectedIndex === i) this.selectedIndex = -1
    else if (this.selectedIndex > i) this.selectedIndex--
    this._updateUI()
    this._syncFormFields()
  }

  _syncFormFields() {
    this.element.dispatchEvent(new CustomEvent("screws:changed", {
      bubbles: true,
      detail: { screws: this.screws }
    }))
  }

  undo() {
    if (this.markers.length === 0) return
    const marker = this.markers.pop()
    marker.traverse(child => { child.geometry?.dispose(); child.material?.dispose() })
    this.scene.remove(marker)
    this.screws.pop()
    this._updateUI()
    this._syncFormFields()
  }

  clearAll() {
    while (this.markers.length > 0) {
      const m = this.markers.pop()
      m.traverse(child => { child.geometry?.dispose(); child.material?.dispose() })
      this.scene.remove(m)
    }
    this.screws = []
    this.selectedIndex = -1
    this._updateUI()
    this._syncFormFields()
  }

  toggleWireframe() {
    this.meshTargets.forEach(m => { m.material.wireframe = !m.material.wireframe })
  }

  getScrews() { return this.screws }

  animate() {
    this.animationId = requestAnimationFrame(() => this.animate())
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
  }
}
