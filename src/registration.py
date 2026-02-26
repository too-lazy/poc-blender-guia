"""Registro (alineación) entre radiografía y modelo 3D basado en landmarks."""
import numpy as np
import json
import sys


def collect_landmarks_interactive(radiograph_data, num_landmarks=3):
    """Recoge landmarks interactivamente desde la terminal.

    Solicita al usuario coordenadas 2D (en la radiografía) y 3D (en el modelo)
    para cada landmark.

    Args:
        radiograph_data: dict retornado por radiograph.load_radiograph.
        num_landmarks: número mínimo de landmarks (default 3).

    Returns:
        dict con 'points_2d' (Nx2) y 'points_3d' (Nx3) como numpy arrays.
    """
    w, h = radiograph_data['width'], radiograph_data['height']
    print(f"\n=== Registro de landmarks ===")
    print(f"Radiografía: {w}x{h} píxeles")
    print(f"Se requieren al menos {num_landmarks} landmarks.\n")

    points_2d = []
    points_3d = []
    i = 0

    while True:
        i += 1
        print(f"--- Landmark {i} ---")

        # Coordenada 2D en la radiografía
        coord_2d = _input_2d(f"  Posición en radiografía (x,y píxeles, 0-{w} x 0-{h}): ")
        if coord_2d is None:
            if len(points_2d) >= num_landmarks:
                break
            print(f"  Se necesitan al menos {num_landmarks} landmarks. Tienes {len(points_2d)}.")
            i -= 1
            continue

        # Coordenada 3D en el modelo
        coord_3d = _input_3d(f"  Posición en modelo 3D (x,y,z): ")
        if coord_3d is None:
            i -= 1
            continue

        points_2d.append(coord_2d)
        points_3d.append(coord_3d)
        print(f"  ✓ Landmark {i}: 2D={coord_2d} → 3D={coord_3d}")

        if i >= num_landmarks:
            more = input(f"\n  ¿Agregar otro landmark? (s/N): ").strip().lower()
            if more != 's':
                break

    return {
        'points_2d': np.array(points_2d, dtype=np.float64),
        'points_3d': np.array(points_3d, dtype=np.float64),
    }


def load_landmarks_json(filepath):
    """Carga landmarks desde un archivo JSON.

    Formato esperado:
    {
        "landmarks": [
            {"name": "molar_sup_der", "image": [120, 200], "model": [0.5, -1.2, 0.3]},
            ...
        ]
    }

    Returns:
        dict con 'points_2d' (Nx2) y 'points_3d' (Nx3) como numpy arrays,
        más 'names' (lista de nombres).
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    landmarks = data['landmarks']
    points_2d = np.array([lm['image'] for lm in landmarks], dtype=np.float64)
    points_3d = np.array([lm['model'] for lm in landmarks], dtype=np.float64)
    names = [lm.get('name', f'landmark_{i}') for i, lm in enumerate(landmarks)]

    print(f"Cargados {len(landmarks)} landmarks desde {filepath}")
    for name, p2, p3 in zip(names, points_2d, points_3d):
        print(f"  {name}: 2D={p2} → 3D={p3}")

    return {
        'points_2d': points_2d,
        'points_3d': points_3d,
        'names': names,
    }


def save_landmarks_json(landmarks_data, filepath):
    """Guarda landmarks a un archivo JSON."""
    landmarks = []
    names = landmarks_data.get('names', [])
    for i, (p2, p3) in enumerate(zip(
        landmarks_data['points_2d'].tolist(),
        landmarks_data['points_3d'].tolist()
    )):
        name = names[i] if i < len(names) else f'landmark_{i}'
        landmarks.append({'name': name, 'image': p2, 'model': p3})

    with open(filepath, 'w') as f:
        json.dump({'landmarks': landmarks}, f, indent=2)

    print(f"Landmarks guardados en: {filepath}")


def detect_landmarks_auto(radiograph_data, max_points=6):
    """Detección automática de landmarks candidatos usando procesamiento de imagen.

    Usa detección de bordes y contornos para sugerir puntos de interés
    en la radiografía (puntas de cúspides, bordes incisales, etc.).

    Args:
        radiograph_data: dict retornado por radiograph.load_radiograph.
        max_points: número máximo de candidatos a retornar.

    Returns:
        numpy array (Nx2) con coordenadas candidatas en la imagen.
    """
    try:
        import cv2
    except ImportError:
        print("OpenCV no disponible para detección automática.")
        return np.array([])

    image = radiograph_data['image']
    img_uint8 = (np.clip(image, 0, 1) * 255).astype(np.uint8)

    # Asegurar imagen en escala de grises
    if len(img_uint8.shape) == 3:
        img_uint8 = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2GRAY)

    # Detección de bordes
    blurred = cv2.GaussianBlur(img_uint8, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Encontrar contornos
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        print("No se detectaron contornos.")
        return np.array([])

    # Ordenar por área (más grandes primero = estructuras dentales principales)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    candidates = []
    for contour in contours[:max_points * 2]:
        # Punto más alto del contorno (punta de cúspide)
        topmost = tuple(contour[contour[:, :, 1].argmin()][0])
        candidates.append(topmost)

        # Centroide del contorno
        M = cv2.moments(contour)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            candidates.append((cx, cy))

    # Eliminar duplicados cercanos
    candidates = _remove_nearby_points(np.array(candidates, dtype=np.float64),
                                        min_distance=20)

    candidates = candidates[:max_points]
    print(f"Detectados {len(candidates)} landmarks candidatos:")
    for i, pt in enumerate(candidates):
        print(f"  Candidato {i+1}: ({pt[0]:.0f}, {pt[1]:.0f})")

    return candidates


def compute_registration(landmarks_data, image_width, image_height):
    """Calcula la transformación rígida (rotación + traslación + escala) entre landmarks.

    Usa mínimos cuadrados para encontrar la mejor transformación que mapea
    los puntos 2D de la radiografía a los puntos 3D del modelo.

    Args:
        landmarks_data: dict con 'points_2d' (Nx2) y 'points_3d' (Nx3).
        image_width: ancho de la imagen en píxeles.
        image_height: alto de la imagen en píxeles.

    Returns:
        dict con:
            - 'scale': factor de escala (píxeles → unidades 3D)
            - 'translation': vector traslación (3,)
            - 'rotation_z': ángulo de rotación en el plano XY (radianes)
            - 'error': error RMS de la alineación
    """
    from scipy.spatial.transform import Rotation
    from scipy.optimize import least_squares

    pts_2d = landmarks_data['points_2d']
    pts_3d = landmarks_data['points_3d']

    if len(pts_2d) < 3:
        raise ValueError("Se necesitan al menos 3 landmarks para el registro.")

    # Normalizar coordenadas 2D al rango [-0.5, 0.5]
    pts_2d_norm = pts_2d.copy()
    pts_2d_norm[:, 0] = (pts_2d_norm[:, 0] / image_width) - 0.5
    pts_2d_norm[:, 1] = (pts_2d_norm[:, 1] / image_height) - 0.5

    # Usar solo XY del 3D para alinear con el plano de la radiografía
    pts_3d_xy = pts_3d[:, :2]

    # Estimar transformación 2D: scale, rotation, translation
    # Minimizar: ||scale * R @ pts_2d_norm + t - pts_3d_xy||²
    def residuals(params):
        scale, angle, tx, ty = params
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        R = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        transformed = scale * (pts_2d_norm @ R.T) + np.array([tx, ty])
        return (transformed - pts_3d_xy).ravel()

    # Estimación inicial
    ptp_2d = np.ptp(pts_2d_norm, axis=0).max()
    ptp_3d = np.ptp(pts_3d_xy, axis=0).max()
    scale_init = ptp_3d / ptp_2d if ptp_2d > 1e-10 else 1.0
    x0 = [scale_init, 0.0,
          pts_3d_xy[:, 0].mean(), pts_3d_xy[:, 1].mean()]

    result = least_squares(residuals, x0)

    scale, angle, tx, ty = result.x
    rms_error = np.sqrt(np.mean(result.fun ** 2))

    # Z promedio de los puntos 3D (altura del plano)
    z_offset = pts_3d[:, 2].mean()

    registration = {
        'scale': float(abs(scale)),
        'translation': [float(tx), float(ty), float(z_offset)],
        'rotation_z': float(angle),
        'error_rms': float(rms_error),
    }

    print(f"\n=== Resultado del registro ===")
    print(f"  Escala: {registration['scale']:.4f}")
    print(f"  Rotación Z: {np.degrees(registration['rotation_z']):.2f}°")
    print(f"  Traslación: ({tx:.4f}, {ty:.4f}, {z_offset:.4f})")
    print(f"  Error RMS: {registration['error_rms']:.6f}")

    return registration


def apply_registration(plane, registration, image_width, image_height):
    """Aplica la transformación de registro al plano de referencia en Blender.

    Args:
        plane: objeto plano de Blender.
        registration: dict retornado por compute_registration.
        image_width: ancho de la imagen original.
        image_height: alto de la imagen original.
    """
    import bpy
    from mathutils import Euler

    scale = registration['scale']
    tx, ty, tz = registration['translation']
    angle = registration['rotation_z']

    # Posicionar el plano
    plane.location = (tx, ty, tz)
    plane.rotation_euler = Euler((0, 0, angle), 'XYZ')

    # Escalar: el plano fue creado con aspect ratio, ahora aplicar scale del registro
    aspect = image_width / image_height
    plane.scale = (scale * aspect, scale, 1.0)

    print(f"Plano posicionado en: ({tx:.3f}, {ty:.3f}, {tz:.3f})")
    print(f"Rotación: {np.degrees(angle):.2f}°, Escala: {scale:.4f}")


def auto_register(radiograph_data, dental_obj):
    """Registro automático sin landmarks manuales.

    Alinea la radiografía con el modelo 3D usando análisis geométrico:
    1. Extrae el bounding box del modelo (proyección XY)
    2. Detecta la región dental en la radiografía (contorno más brillante)
    3. Calcula escala + traslación para alinear ambos

    Args:
        radiograph_data: dict retornado por radiograph.load_radiograph.
        dental_obj: objeto Blender del modelo dental.

    Returns:
        dict de registro (scale, translation, rotation_z, error_rms).
    """
    import bpy
    from mathutils import Vector

    # 1. Obtener geometría del modelo 3D (proyección XY)
    bbox = [dental_obj.matrix_world @ Vector(c) for c in dental_obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]

    model_cx = (min(xs) + max(xs)) / 2
    model_cy = (min(ys) + max(ys)) / 2
    model_w = max(xs) - min(xs)
    model_h = max(ys) - min(ys)
    model_z = min(zs)

    # 2. Detectar región dental en la radiografía
    img_w = radiograph_data['width']
    img_h = radiograph_data['height']

    try:
        import cv2
        image = radiograph_data['image']
        img_uint8 = (np.clip(image, 0, 1) * 255).astype(np.uint8)
        if len(img_uint8.shape) == 3:
            img_uint8 = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2GRAY)

        # Umbralizar para encontrar la región dental (brillo > media)
        _, thresh = cv2.threshold(img_uint8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Usar el contorno más grande como región dental
            largest = max(contours, key=cv2.contourArea)
            rx, ry, rw, rh = cv2.boundingRect(largest)
            radio_cx = rx + rw / 2
            radio_cy = ry + rh / 2
        else:
            radio_cx, radio_cy = img_w / 2, img_h / 2
            rw, rh = img_w * 0.8, img_h * 0.6
    except ImportError:
        # Sin OpenCV, usar centro de la imagen
        radio_cx, radio_cy = img_w / 2, img_h / 2
        rw, rh = img_w * 0.8, img_h * 0.6

    # 3. Calcular transformación
    # Escala: relación entre tamaño del modelo y tamaño de la región en la imagen
    scale_x = model_w / (rw / img_w) if rw > 0 else model_w
    scale_y = model_h / (rh / img_h) if rh > 0 else model_h
    scale = (scale_x + scale_y) / 2

    # Traslación: centrar el plano sobre el modelo
    tx = model_cx
    ty = model_cy
    tz = model_z - 0.5  # Ligeramente debajo del modelo

    registration = {
        'scale': float(scale),
        'translation': [float(tx), float(ty), float(tz)],
        'rotation_z': 0.0,
        'error_rms': 0.0,
    }

    print(f"\n=== Registro automático ===")
    print(f"  Región dental en radiografía: centro=({radio_cx:.0f}, {radio_cy:.0f}), "
          f"tamaño={rw:.0f}x{rh:.0f} px")
    print(f"  Modelo 3D: centro=({model_cx:.2f}, {model_cy:.2f}), "
          f"tamaño={model_w:.2f}x{model_h:.2f}")
    print(f"  Escala: {registration['scale']:.4f}")
    print(f"  Posición plano: ({tx:.3f}, {ty:.3f}, {tz:.3f})")

    return registration


# --- Funciones auxiliares ---

def _input_2d(prompt):
    """Lee coordenadas 2D del usuario. Retorna None para salir."""
    try:
        raw = input(prompt).strip()
        if raw.lower() in ('', 'q', 'quit', 'done'):
            return None
        parts = [float(x.strip()) for x in raw.replace(';', ',').split(',')]
        if len(parts) != 2:
            print("  Error: se esperan 2 valores (x, y)")
            return None
        return parts
    except (ValueError, EOFError):
        return None


def _input_3d(prompt):
    """Lee coordenadas 3D del usuario. Retorna None para salir."""
    try:
        raw = input(prompt).strip()
        if raw.lower() in ('', 'q', 'quit', 'done'):
            return None
        parts = [float(x.strip()) for x in raw.replace(';', ',').split(',')]
        if len(parts) != 3:
            print("  Error: se esperan 3 valores (x, y, z)")
            return None
        return parts
    except (ValueError, EOFError):
        return None


def _remove_nearby_points(points, min_distance=20):
    """Elimina puntos que están demasiado cerca entre sí."""
    if len(points) == 0:
        return points

    filtered = [points[0]]
    for pt in points[1:]:
        distances = [np.linalg.norm(pt - f) for f in filtered]
        if min(distances) >= min_distance:
            filtered.append(pt)

    return np.array(filtered)
