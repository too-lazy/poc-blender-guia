import { Controller } from "@hotwired/stimulus"

// Interactive 3D STL viewer using Three.js (loaded from CDN).
// Usage: <div data-controller="stl-viewer" data-stl-viewer-url-value="/path/to/file.stl">
export default class extends Controller {
  static values = { url: String }

  async connect() {
    this.canvas = this.element.querySelector("[data-stl-viewer-target='canvas']")
    if (!this.canvas) {
      this.canvas = document.createElement("div")
      this.canvas.style.cssText = "width:100%;height:500px;"
      this.element.querySelector("[data-stl-viewer-target='container']")?.appendChild(this.canvas)
        || this.element.appendChild(this.canvas)
    }

    this.showLoading()
    await this.loadThreeJS()
    this.initScene()
    await this.loadSTL()
    this.hideLoading()
    this.animate()
  }

  disconnect() {
    if (this.animationId) cancelAnimationFrame(this.animationId)
    if (this.renderer) {
      this.renderer.dispose()
      this.renderer.domElement.remove()
    }
    window.removeEventListener("resize", this.onResize)
  }

  showLoading() {
    this.loadingEl = document.createElement("div")
    this.loadingEl.style.cssText = `
      position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
      background:#FFFBF5;z-index:10;
    `
    this.loadingEl.innerHTML = `
      <div style="text-align:center">
        <div style="font-size:24px;margin-bottom:8px">🦷</div>
        <div style="font-weight:800;font-size:14px;color:#6366F1">Loading 3D model…</div>
      </div>
    `
    this.canvas.style.position = "relative"
    this.canvas.appendChild(this.loadingEl)
  }

  hideLoading() {
    if (this.loadingEl) this.loadingEl.remove()
  }

  async loadThreeJS() {
    if (window.THREE) return

    const CDN = "https://cdn.jsdelivr.net/npm/three@0.170.0"

    await new Promise((resolve, reject) => {
      const s = document.createElement("script")
      s.src = `${CDN}/build/three.min.js`
      s.onload = resolve
      s.onerror = reject
      document.head.appendChild(s)
    })

    // Load OrbitControls & STLLoader as global scripts
    await Promise.all([
      new Promise((resolve, reject) => {
        const s = document.createElement("script")
        s.src = `${CDN}/examples/js/controls/OrbitControls.js`
        s.onload = resolve
        s.onerror = reject
        document.head.appendChild(s)
      }),
      new Promise((resolve, reject) => {
        const s = document.createElement("script")
        s.src = `${CDN}/examples/js/loaders/STLLoader.js`
        s.onload = resolve
        s.onerror = reject
        document.head.appendChild(s)
      })
    ])
  }

  initScene() {
    const THREE = window.THREE
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

    // OrbitControls
    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement)
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

    // Resize handler
    this.onResize = () => {
      const w = this.canvas.clientWidth
      const h = this.canvas.clientHeight || 500
      this.camera.aspect = w / h
      this.camera.updateProjectionMatrix()
      this.renderer.setSize(w, h)
    }
    window.addEventListener("resize", this.onResize)
  }

  async loadSTL() {
    const THREE = window.THREE
    const loader = new THREE.STLLoader()

    return new Promise((resolve, reject) => {
      loader.load(
        this.urlValue,
        (geometry) => {
          // Bone-colored material matching Blender pipeline
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
          const box = geometry.boundingBox
          const center = new THREE.Vector3()
          box.getCenter(center)
          geometry.translate(-center.x, -center.y, -center.z)

          // Fit camera to model
          const size = new THREE.Vector3()
          box.getSize(size)
          const maxDim = Math.max(size.x, size.y, size.z)
          const fov = this.camera.fov * (Math.PI / 180)
          const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.5

          this.camera.position.set(dist * 0.5, dist * 0.5, dist)
          this.camera.lookAt(0, 0, 0)
          this.controls.target.set(0, 0, 0)
          this.controls.update()

          this.scene.add(mesh)
          this.mesh = mesh
          resolve()
        },
        undefined,
        (error) => {
          console.error("STL load error:", error)
          this.hideLoading()
          this.canvas.innerHTML = `<div style="padding:40px;text-align:center;color:#991b1b;font-weight:bold">
            ⚠ Failed to load 3D model</div>`
          reject(error)
        }
      )
    })
  }

  animate() {
    this.animationId = requestAnimationFrame(() => this.animate())
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
  }

  // Reset camera to default position
  resetView() {
    if (!this.mesh) return
    const box = new window.THREE.Box3().setFromObject(this.mesh)
    const size = new window.THREE.Vector3()
    box.getSize(size)
    const maxDim = Math.max(size.x, size.y, size.z)
    const fov = this.camera.fov * (Math.PI / 180)
    const dist = maxDim / (2 * Math.tan(fov / 2)) * 1.5

    this.camera.position.set(dist * 0.5, dist * 0.5, dist)
    this.camera.lookAt(0, 0, 0)
    this.controls.target.set(0, 0, 0)
    this.controls.update()
  }

  // Toggle wireframe
  toggleWireframe() {
    if (!this.mesh) return
    this.mesh.material.wireframe = !this.mesh.material.wireframe
  }
}
