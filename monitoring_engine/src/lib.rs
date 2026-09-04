use pyo3::prelude::*;
use pyo3::types::PyDict;
use sysinfo::{System, Disk, Disks};
use ahash::AHashMap as HashMap;
use std::fs;
use std::path::Path;
use pythonize::{depythonize, pythonize};
use serde_json::Value;

// ═══════════════════════════════════════════════════════════
// MONITORING ENGINE — Pemindaian Disk, Info Sistem, Pembersihan
// ═══════════════════════════════════════════════════════════

// Add #[pyclass] to make it a Python object
#[pyclass]
#[derive(Debug, Clone)]
pub struct DiskInfo {
    #[pyo3(get)] // Exposes the property to Python
    pub path: String,
    
    #[pyo3(get)]
    pub name: String,
    
    #[pyo3(get)]
    pub total_bytes: u64,
    
    #[pyo3(get)]
    pub used_bytes: u64,
    
    #[pyo3(get)]
    pub free_bytes: u64,
    
    #[pyo3(get)]
    pub percent_used: f64,
}

// ═══════════════════════════════════════════════
// BAGIAN 1: PEMINDAIAN SEMUA DRIVE
// ═══════════════════════════════════════════════

#[pyfunction]
fn scan_all_drives() -> PyResult<Vec<DiskInfo>> {
    let disks = Disks::new_with_refreshed_list();
    let mut result = Vec::with_capacity(8);

    for disk in disks.list() {
        let mount_point = disk.mount_point().to_string_lossy().to_string();
        let name = disk.name().to_string_lossy().to_string();
        let total = disk.total_space();
        let free = disk.available_space();
        let used = total - free;
        let percent = if total > 0 { (used as f64 / total as f64) * 100.0 } else { 0.0 };

        result.push(DiskInfo {
            path: mount_point,
            name,
            total_bytes: total,
            used_bytes: used,
            free_bytes: free,
            percent_used: percent,
        });
    }

    Ok(result)
}

// ═══════════════════════════════════════════════
// BAGIAN 2: FORMAT SATUAN (Byte → KB/MB/GB/TB)
// ═══════════════════════════════════════════════

#[pyfunction]
fn format_bytes(bytes: u64) -> PyResult<String> {
    let units = ["B", "KB", "MB", "GB", "TB"];
    let mut value = bytes as f64;
    let mut unit_index = 0;

    while value >= 1024.0 && unit_index < 4 {
        value /= 1024.0;
        unit_index += 1;
    }

    Ok(format!("{:.2} {}", value, units[unit_index]))
}

#[pyfunction]
fn split_bytes(bytes: u64) -> PyResult<(f64, String)> {
    let units = ["B", "KB", "MB", "GB", "TB"];
    let mut value = bytes as f64;
    let mut unit_index = 0;

    while value >= 1024.0 && unit_index < 4 {
        value /= 1024.0;
        unit_index += 1;
    }

    Ok((value, units[unit_index].to_string()))
}

// ═══════════════════════════════════════════════
// BAGIAN 3: PEMBERSIHAN FILE SEMENTARA
// ═══════════════════════════════════════════════

/// Hitung total ukuran sebuah folder secara rekursif (dipakai untuk statistik
/// freed_bytes sebelum folder itu dihapus — ukurannya nggak bisa dibaca lagi
/// setelah dihapus).
fn dir_size_recursive(path: &Path) -> u64 {
    let mut total = 0u64;
    if let Ok(entries) = fs::read_dir(path) {
        for entry in entries.flatten() {
            let p = entry.path();
            if let Ok(md) = entry.metadata() {
                if md.is_dir() {
                    total += dir_size_recursive(&p);
                } else {
                    total += md.len();
                }
            }
        }
    }
    total
}

#[pyfunction]
fn clear_temp_files(folder_path: &str) -> PyResult<(u32, u64, u32)> {
    // → Mengembalikan (item_dihapus, total_byte_dibersihkan, item_gagal)
    // Menghapus SEMUA item langsung di dalam folder_path (file maupun
    // subfolder, dihapus rekursif) — setara `os.unlink` + `shutil.rmtree`
    // versi Python-nya, tapi jalan native tanpa GIL.
    let path = Path::new(folder_path);
    if !path.exists() {
        return Ok((0, 0, 0));
    }

    let mut deleted = 0u32;
    let mut failed = 0u32;
    let mut freed_bytes = 0u64;

    if let Ok(entries) = fs::read_dir(path) {
        for entry in entries.flatten() {
            let p = entry.path();
            let md = match entry.metadata() {
                Ok(m) => m,
                Err(_) => {
                    failed += 1;
                    continue;
                }
            };

            if md.is_dir() {
                let size = dir_size_recursive(&p);
                match fs::remove_dir_all(&p) {
                    Ok(_) => {
                        deleted += 1;
                        freed_bytes += size;
                    }
                    Err(_) => failed += 1,
                }
            } else {
                // Menutupi file biasa maupun symlink.
                let size = md.len();
                match fs::remove_file(&p) {
                    Ok(_) => {
                        deleted += 1;
                        freed_bytes += size;
                    }
                    Err(_) => failed += 1,
                }
            }
        }
    }

    Ok((deleted, freed_bytes, failed))
}

// ═══════════════════════════════════════════════
// BAGIAN 4: INFORMASI SISTEM (RAM)
// ═══════════════════════════════════════════════

#[pyfunction]
fn get_system_ram() -> PyResult<(u64, u64)> {
    // → (total_bytes, dipakai_bytes)
    let mut sys = System::new();
    sys.refresh_memory();
    Ok((sys.total_memory(), sys.used_memory()))
}

// ═══════════════════════════════════════════════
// BAGIAN 5: INFORMASI PER DRIVE SATUAN
// ═══════════════════════════════════════════════

#[pyfunction]
fn get_drive_info(mount_path: &str) -> PyResult<(u64, u64, u64, f64)> {
    // → (total, digunakan, tersedia, persen_terpakai)
    let disks = Disks::new_with_refreshed_list();

    for disk in disks.list() {
        if disk.mount_point().to_string_lossy() == mount_path {
            let total = disk.total_space();
            let free = disk.available_space();
            let used = total - free;
            let percent = if total > 0 { (used as f64 / total as f64) * 100.0 } else { 0.0 };
            return Ok((total, used, free, percent));
        }
    }

    Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
        format!("Drive tidak ditemukan: {}", mount_path)
    ))
}

// ═══════════════════════════════════════════════
// BAGIAN 6: KONFIGURASI JSON (dipakai JsonSettings)
// ═══════════════════════════════════════════════
// Dipakai buat gantiin json.load()/json.dump() Python murni di JsonSettings
// (macan_monitoring_new49.py) — file config .json dibaca/ditulis di HAMPIR
// SEMUA widget (tiap widget punya file .json sendiri, dan setValue() nge-
// flush ke disk setiap kali dipanggil), jadi parsing/serialize yang lebih
// cepat + write atomic native (tanpa lewat interpreter Python) kerasa di
// startup semua widget sekaligus maupun saat drag/resize yang sering
// nge-trigger setValue().
//
// Pola pemakaian di Python (lihat JsonSettings._load / .sync): dibungkus
// try/except dan SELALU ada fallback ke json.load/json.dump murni Python
// kalau wheel Rust-nya belum ke-build di mesin itu — sama seperti
// clear_temp_files di atas.

/// Baca & parse file JSON langsung jadi dict Python. File yang belum ada
/// dianggap config kosong (dict kosong), BUKAN error — ini konsisten sama
/// perilaku JsonSettings._load() versi Python-nya.
#[pyfunction]
fn load_json_file(py: Python<'_>, path: &str) -> PyResult<PyObject> {
    let p = Path::new(path);
    if !p.exists() {
        return Ok(PyDict::new_bound(py).into());
    }

    let text = fs::read_to_string(p).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("gagal baca {}: {}", path, e))
    })?;

    let value: Value = serde_json::from_str(&text).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("JSON rusak di {}: {}", path, e))
    })?;

    let obj = pythonize(py, &value).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("konversi JSON->Python gagal: {}", e))
    })?;

    Ok(obj.into())
}

/// Serialize dict Python -> JSON lalu tulis SECARA ATOMIC (tulis ke
/// "<path>.tmp" dulu, baru rename ke path asli) — sama persis semantiknya
/// dengan sync() versi Python (tulis-lalu-rename supaya nggak ada file
/// setengah-tertulis/korup kalau proses ke-interrupt di tengah jalan).
#[pyfunction]
fn save_json_file(path: &str, data: &Bound<'_, PyAny>) -> PyResult<()> {
    let value: Value = depythonize(data).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("konversi Python->JSON gagal: {}", e))
    })?;

    let text = serde_json::to_string_pretty(&value).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("gagal serialize JSON: {}", e))
    })?;

    let tmp_path = format!("{}.tmp", path);
    fs::write(&tmp_path, text).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("gagal tulis {}: {}", tmp_path, e))
    })?;
    fs::rename(&tmp_path, path).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("gagal rename {} -> {}: {}", tmp_path, path, e))
    })?;

    Ok(())
}

// ═══════════════════════════════════════════════
// DAFTAR FUNGSI KE PYTHON
// ═══════════════════════════════════════════════

#[pymodule]
fn monitoring_engine(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(scan_all_drives, m)?)?;
    m.add_function(wrap_pyfunction!(format_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(split_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(clear_temp_files, m)?)?;
    m.add_function(wrap_pyfunction!(get_system_ram, m)?)?;
    m.add_function(wrap_pyfunction!(get_drive_info, m)?)?;
    m.add_function(wrap_pyfunction!(load_json_file, m)?)?;
    m.add_function(wrap_pyfunction!(save_json_file, m)?)?;
    Ok(())
}