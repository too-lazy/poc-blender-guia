import { Controller } from "@hotwired/stimulus"

// Interactive 3D STL viewer using Three.js (loaded from CDN).
// Usage: <div data-controller="stl-viewer" data-stl-viewer-url-value="/path/to/file.stl">
export default class extends Controller {
  static values = { url: String }

  async connect() {
    this.canvas = this.element.querySelector("[data-stl-viewer-target='container']")
    if (!this.canvas) return

    this.showLoading()

    try {
      await this.loadThreeJS()
      this.initScene()
      await this.loadSTL()
      this.hideLoading()
      this.animate()
    } catch (e) {
      console.error("STL Viewer error:", e)
      this.hideLoading()
      this.canvas.innerHTML = `<div style="padding:40px;text-align:center;color:#991b1b;font-weight:bold">
        ⚠ Failed to load 3D viewer: ${e.message}</div>`
    }
  }

  disconnect() {
    if (this.animationId) cancelAnimationFrame(this.animationId)
    if (this.renderer) {
      this.renderer.dispose()
      this.renderer.domElement.remove()
    }
    if (this._onResize) window.removeEventListener("resize", this._onResize)
  }

  showLoading() {
    this.loadingEl = document.createElement("div")
    this.loadingEl.style.cssText = `
      display:flex;align-items:center;justify-content:center;
      width:100%;height:100%;background:#FFFBF5;
    `
    this.loadingEl.innerHTML = `
      <div style="text-align:center">
        <div style="font-size:24px;margin-bottom:8px">🦷</div>
        <div style="font-weight:800;font-size:14px;color:#6366F1">Loading 3D model…</div>
      </div>
    `
    this.canvas.appendChild(this.loadingEl)
  }

  hideLoading() {
    if (this.loadingEl) this.loadingEl.remove()
  }

  async loadThreeJS() {
    if (this.THREE) return

    const CDN = "https://esm.sh/three@0.170.0"

    const [threeModule, controlsModule, loaderModule] = await Promise.all([
      import(CDN),
      import(`${CDN}/examples/jsm/controls/OrbitControls.js`),
      import(`${CDN}/examples/jsm/loaders/STLLoader.js`)
    ])

    this.THREE = threeModule
    this.OrbitControls = controlsModule.OrbitControls
    this.STLLoader = loaderModule.STLLoader
  }

  initScene() {
    const THREE = this.THREE
    const w = this.canvas.clientWidth
    const h = this.canvas.clientHeight || 500

    this.scene = new THREE.Scene()
    this.scene.background = new THREE.Color(0xFFFBF5)

    this.camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 1000)
    this.camera.position.set(0, 0, 100)

    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setSize(w, h)
    this.renderer.setPixelRatio(window.devicePixelRatio)
    this.renderer.shadowMap.enabled = true
    this.canvas.appendChild(this.renderer.domElement)

    this.controls = new this.OrbitControls(this.camera, this.renderer.domElement)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.08
    this.controls.rotateSpeed = 0.8

    // Lighting
    const ambient = new THREE.AmbientLight(0xffffff, 0.6)
    this.scene.add(ambient)

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0)
    dirLight.position.set(50, 80, 50)
    dirLight.castShadow = true
    this.scene.add(dirLight)

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.4)
    fillLight.position.set(-30, -20, 40)
    this.scene.add(fillLight)

    // Grid
    const grid = new THREE.GridHelper(200, 20, 0xcccccc, 0xe5e5e5)
    grid.rotation.x = Math.PI / 2
    this.scene.add(grid)

    this._onResize = () => {
      const w = this.canvas.clientWidth
      const h = this.canvas.clientHeight || 500
      this.camera.aspect = w / h
      this.camera.updateProjectionMatrix()
      this.renderer.setSize(w, h)
    }
    window.addEventListener("resize", this._onResize)
  }

  async loadSTL() {
    const THREE = this.THREE
    const loader = new this.STLLoader()

    const response = await fetch(this.urlValue)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const buffer = await response.arrayBuffer()
    const geometry = loader.parse(buffer)

    const material = new THREE.MeshPhysicalMaterial({
      color: 0xE6D9BF,
      roughness: 0.4,
      metalness: 0.0,
      clearcoat: 0.1,
    })

    const mesh = new THREE.Mesh(geometry, material)
    mesh.castShadow = true
    mesh.receiveShadow = true

    // Center geometry
    geometry.computeBoundingBox()
    const center = new THREE.Vector3()
    geometry.boundingBox.getCenter(center)
    geometry.translate(-center.x, -center.y, -center.z)

    // Fit camera
    const size = new THREE.Vector3()
    geometry.boundingBox.getSize(size)
    const maxDim = Math.max(size.x, size.y, size.z)
    const fov = this.camera.fov * (Math.PI / 180)
    const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.5

    this.camera.position.set(dist * 0.5, dist * 0.5, dist)
    this.camera.lookAt(0, 0, 0)
    this.controls.target.set(0, 0, 0)
    this.controls.update()

    this.scene.add(mesh)
    this.mesh = mesh
  }

  animate() {
    this.animationId = requestAnimationFrame(() => this.animate())
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
  }

  resetView() {
    if (!this.mesh) return
    const THREE = this.THREE
    const box = new THREE.Box3().setFromObject(this.mesh)
    const size = new THREE.Vector3()
    box.getSize(size)
    const maxDim = Math.max(size.x, size.y, size.z)
    const fov = this.camera.fov * (Math.PI / 180)
    const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.5

    this.camera.position.set(dist * 0.5, dist * 0.5, dist)
    this.camera.lookAt(0, 0, 0)
    this.controls.target.set(0, 0, 0)
    this.controls.update()
  }

  toggleWireframe() {
    if (!this.mesh) return
    this.mesh.material.wireframe = !this.mesh.material.wireframe
  }
}
