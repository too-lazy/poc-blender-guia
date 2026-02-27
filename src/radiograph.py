"""Carga y procesamiento de radiografías (DICOM single-slice, CBCT multi-slice y 2D)."""
import os
import numpy as np


def load_radiograph(filepath):
    """Carga una radiografía desde DICOM o imagen 2D.

    Args:
        filepath: Ruta al archivo (DICOM, PNG, JPEG, TIFF).

    Returns:
        dict con:
            - 'image': numpy array normalizado [0, 1] float32 (H, W) o (H, W, C)
            - 'width': ancho en píxeles
            - 'height': alto en píxeles
            - 'format': 'dicom' o 'image'
            - 'metadata': dict con info adicional (spacing, modality, etc.)
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext in ('.dcm', '.dicom') or _is_dicom(filepath):
        return _load_dicom(filepath)
    else:
        return _load_image(filepath)


def load_dicom_series(directory, series_filter=None):
    """Carga una serie DICOM multi-slice (CBCT) como volumen 3D.

    Busca todos los archivos DICOM en el directorio, los ordena por
    posición de slice y los apila en un volumen 3D.

    Args:
        directory: Ruta al directorio con archivos DICOM (ej. CT3/).
        series_filter: Filtro opcional por SeriesDescription (ej. 'CTVolume').
            Si None, usa todos los archivos DICOM encontrados.

    Returns:
        dict con:
            - 'volume': numpy array float32 (D, H, W) normalizado [0, 1]
            - 'width': ancho en píxeles
            - 'height': alto en píxeles
            - 'depth': número de slices
            - 'spacing': (row_spacing, col_spacing, slice_thickness) en mm
            - 'format': 'cbct'
            - 'metadata': dict con info adicional
    """
    try:
        import pydicom
    except ImportError:
        raise ImportError("pydicom es requerido para cargar DICOM: pip install pydicom")

    if not os.path.isdir(directory):
        raise NotADirectoryError(f"No es un directorio: {directory}")

    # Recopilar archivos DICOM válidos
    slices = []
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue
        if not _is_dicom(fpath):
            continue
        try:
            ds = pydicom.dcmread(fpath, stop_before_pixels=True, force=True)
        except Exception:
            continue

        if series_filter and getattr(ds, 'SeriesDescription', '') != series_filter:
            continue

        slices.append((fpath, ds))

    if not slices:
        raise FileNotFoundError(
            f"No se encontraron archivos DICOM en: {directory}"
            + (f" (filtro: {series_filter})" if series_filter else "")
        )

    # Ordenar por ImagePositionPatient[2] (posición axial Z) o InstanceNumber
    def _sort_key(item):
        ds = item[1]
        pos = getattr(ds, 'ImagePositionPatient', None)
        if pos is not None:
            return float(pos[2])
        return int(getattr(ds, 'InstanceNumber', 0))

    slices.sort(key=_sort_key)

    # Leer pixel data de cada slice
    ref_ds = slices[0][1]
    rows = ref_ds.Rows
    cols = ref_ds.Columns
    pixel_arrays = []

    for fpath, _ in slices:
        ds = pydicom.dcmread(fpath)
        arr = ds.pixel_array.astype(np.float32)
        if arr.shape != (rows, cols):
            arr = arr[:rows, :cols]
        pixel_arrays.append(arr)

    volume = np.stack(pixel_arrays, axis=0)  # (D, H, W)

    # Calcular spacing
    pixel_spacing = list(getattr(ref_ds, 'PixelSpacing', [1.0, 1.0]))
    slice_thickness = float(getattr(ref_ds, 'SliceThickness', 0.0))

    # Si no hay SliceThickness, calcular desde posiciones
    if slice_thickness == 0.0 and len(slices) >= 2:
        pos0 = getattr(slices[0][1], 'ImagePositionPatient', None)
        pos1 = getattr(slices[1][1], 'ImagePositionPatient', None)
        if pos0 is not None and pos1 is not None:
            slice_thickness = abs(float(pos1[2]) - float(pos0[2]))

    # Normalizar volumen
    volume = _normalize_minmax(volume)

    metadata = {
        'modality': getattr(ref_ds, 'Modality', 'CT'),
        'series_description': getattr(ref_ds, 'SeriesDescription', ''),
        'patient_id': getattr(ref_ds, 'PatientID', ''),
        'patient_name': str(getattr(ref_ds, 'PatientName', '')),
        'study_date': getattr(ref_ds, 'StudyDate', ''),
        'manufacturer': getattr(ref_ds, 'Manufacturer', ''),
        'pixel_spacing': [float(s) for s in pixel_spacing],
        'slice_thickness': slice_thickness,
        'rows': rows,
        'columns': cols,
        'bits_stored': getattr(ref_ds, 'BitsStored', 0),
        'image_orientation': list(getattr(ref_ds, 'ImageOrientationPatient', [])),
        'image_position_first': list(getattr(slices[0][1], 'ImagePositionPatient', [])),
        'image_position_last': list(getattr(slices[-1][1], 'ImagePositionPatient', [])),
    }

    spacing = (float(pixel_spacing[0]), float(pixel_spacing[1]), slice_thickness)

    print(f"Volumen CBCT cargado: {volume.shape[0]} slices, "
          f"{cols}x{rows} px, spacing {spacing} mm")

    return {
        'volume': volume,
        'width': cols,
        'height': rows,
        'depth': volume.shape[0],
        'spacing': spacing,
        'format': 'cbct',
        'metadata': metadata,
    }


def _is_dicom(filepath):
    """Detecta si un archivo es DICOM leyendo el magic number."""
    try:
        with open(filepath, 'rb') as f:
            f.seek(128)
            return f.read(4) == b'DICM'
    except (IOError, OSError):
        return False


def _load_dicom(filepath):
    """Carga un archivo DICOM y extrae la imagen normalizada."""
    try:
        import pydicom
    except ImportError:
        raise ImportError("pydicom es requerido para cargar DICOM: pip install pydicom")

    ds = pydicom.dcmread(filepath)
    pixel_array = ds.pixel_array.astype(np.float32)

    # Aplicar windowing si está disponible en los metadatos
    wc = getattr(ds, 'WindowCenter', None)
    ww = getattr(ds, 'WindowWidth', None)

    if wc is not None and ww is not None:
        # Manejar valores que pueden ser listas
        wc = wc[0] if hasattr(wc, '__iter__') else float(wc)
        ww = ww[0] if hasattr(ww, '__iter__') else float(ww)
        image = _apply_window(pixel_array, wc, ww)
    else:
        image = _normalize_minmax(pixel_array)

    metadata = {
        'modality': getattr(ds, 'Modality', 'unknown'),
        'patient_id': getattr(ds, 'PatientID', ''),
        'pixel_spacing': list(getattr(ds, 'PixelSpacing', [])),
        'rows': ds.Rows,
        'columns': ds.Columns,
        'bits_stored': getattr(ds, 'BitsStored', 0),
        'window_center': wc,
        'window_width': ww,
    }

    return {
        'image': image,
        'width': ds.Columns,
        'height': ds.Rows,
        'format': 'dicom',
        'metadata': metadata,
    }


def _load_image(filepath):
    """Carga una imagen 2D (PNG, JPEG, TIFF) y la normaliza."""
    try:
        import cv2
    except ImportError:
        # Fallback a Pillow
        try:
            from PIL import Image
            img = Image.open(filepath)
            pixel_array = np.array(img, dtype=np.float32)
        except ImportError:
            raise ImportError(
                "Se requiere opencv-python o Pillow: "
                "pip install opencv-python Pillow"
            )
    else:
        pixel_array = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        if pixel_array is None:
            raise FileNotFoundError(f"No se pudo cargar la imagen: {filepath}")
        pixel_array = pixel_array.astype(np.float32)
        # Convertir BGR a RGB si es color
        if len(pixel_array.shape) == 3 and pixel_array.shape[2] == 3:
            pixel_array = cv2.cvtColor(pixel_array, cv2.COLOR_BGR2RGB)

    image = _normalize_minmax(pixel_array)
    h, w = image.shape[:2]

    metadata = {
        'source_path': filepath,
        'original_dtype': str(pixel_array.dtype),
        'channels': image.shape[2] if len(image.shape) == 3 else 1,
    }

    return {
        'image': image,
        'width': w,
        'height': h,
        'format': 'image',
        'metadata': metadata,
    }


def _apply_window(pixel_array, center, width):
    """Aplica windowing DICOM y normaliza a [0, 1]."""
    lower = center - width / 2
    upper = center + width / 2
    image = np.clip(pixel_array, lower, upper)
    return (image - lower) / (upper - lower)


def _normalize_minmax(pixel_array):
    """Normaliza a [0, 1] usando min-max."""
    vmin = pixel_array.min()
    vmax = pixel_array.max()
    if vmax - vmin == 0:
        return np.zeros_like(pixel_array)
    return (pixel_array - vmin) / (vmax - vmin)


def save_normalized(radiograph_data, output_path):
    """Guarda la imagen normalizada como PNG para verificación.

    Args:
        radiograph_data: dict retornado por load_radiograph.
        output_path: ruta de salida PNG.
    """
    image = (radiograph_data['image'] * 255).astype(np.uint8)

    try:
        import cv2
        if len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, image)
    except ImportError:
        from PIL import Image
        if len(image.shape) == 2:
            pil_img = Image.fromarray(image, mode='L')
        else:
            pil_img = Image.fromarray(image)
        pil_img.save(output_path)

    print(f"Imagen normalizada guardada en: {output_path}")
