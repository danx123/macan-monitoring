use pyo3::prelude::*;
use sysinfo::Components;

#[pyclass]
pub struct TemperatureSensor {
    components: Components,
}

#[pymethods]
impl TemperatureSensor {
    #[new]
    pub fn new() -> Self {
        TemperatureSensor {
            // sysinfo 0.30+: Components sudah lepas dari struct System,
            // jadi cukup dibuat langsung sekali di sini.
            components: Components::new_with_refreshed_list(),
        }
    }

    /// Segarkan data sensor (dipanggil otomatis oleh method di bawah)
    pub fn refresh(&mut self) {
        // Rebuild list-nya biar sensor yang hilang/nambah (mis. saat laptop
        // dicolok charger) ikut ke-update, bukan cuma refresh nilai lama.
        self.components = Components::new_with_refreshed_list();
    }

    /// Ambil semua pembacaan suhu yang tersedia
    /// Return: list of tuple (nama_sensor, suhu_c, suhu_maks)
    pub fn get_all_temperatures(&mut self) -> Vec<(String, f32, f32)> {
        self.refresh();
        self.components
            .iter()
            .map(|comp| {
                (
                    comp.label().to_string(),
                    // sysinfo 0.31: temperature()/max() sekarang Option<f32>
                    // (dulu langsung f32::NAN kalau gagal baca)
                    comp.temperature(),
                    comp.max(),
                )
            })
            .collect()
    }

    /// Rata-rata suhu dari semua sensor (sensor yang gagal dibaca di-skip)
    pub fn get_average_temp(&mut self) -> Option<f32> {
        let readings = self.get_all_temperatures();
        let valid: Vec<f32> = readings
            .into_iter()
            .map(|(_, t, _)| t)
            .filter(|t| !t.is_nan())
            .collect();
        if valid.is_empty() {
            return None;
        }
        Some(valid.iter().sum::<f32>() / valid.len() as f32)
    }

    /// Suhu tertinggi
    pub fn get_highest_temp(&mut self) -> Option<(String, f32)> {
        self.get_all_temperatures()
            .into_iter()
            .filter(|(_, t, _)| !t.is_nan())
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(name, temp, _)| (name, temp))
    }
}

// pyo3 0.22: signature #[pymodule] gil-ref lama (`&PyModule`) sudah dilepas
// dari default (perlu feature "gil-refs" yang gak kita pasang). Pakai
// Bound<'_, PyModule> yang jadi API default sejak 0.21.
#[pymodule]
fn temp_monitor(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TemperatureSensor>()?;
    Ok(())
}