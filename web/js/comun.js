/* Utilidades compartidas por todas las pantallas (cliente de la API, mapas, formatos). */
const CALI = [3.42, -76.52];
// Imagen de reemplazo cuando una foto no está disponible (p. ej. en los datos de demostración)
const FOTO_VACIA = 'data:image/svg+xml,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56"><rect width="56" height="56" fill="#e9ecef"/>' +
  '<path d="M16 38l8-10 6 7 4-5 6 8z" fill="#adb5bd"/><circle cx="22" cy="21" r="4" fill="#adb5bd"/></svg>');

// ---------------------------------------------------------------- API
async function api(metodo, ruta, datos) {
  const op = { method: metodo, credentials: 'same-origin', headers: {} };
  if (datos instanceof FormData) op.body = datos;
  else if (datos !== undefined) { op.body = JSON.stringify(datos); op.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(ruta, op);
  const cuerpo = (r.headers.get('content-type') || '').includes('json') ? await r.json() : await r.text();
  if (!r.ok) {
    const e = new Error((cuerpo && cuerpo.error) || `Error ${r.status}`);
    e.estado = r.status;
    throw e;
  }
  return cuerpo;
}
const get = (ruta) => api('GET', ruta);
const post = (ruta, datos) => api('POST', ruta, datos);
const patch = (ruta, datos) => api('PATCH', ruta, datos);
const borrar = (ruta) => api('DELETE', ruta);

async function sesion(permitido) {
  try {
    const u = await get('/api/sesion');
    if (permitido && !permitido(u)) { location.href = '/'; return; }
    document.querySelectorAll('[data-usuario]').forEach((e) => (e.textContent = `${u.nombre} · ${u.empresa}`));
    return u;
  } catch { location.href = '/'; }
}
async function salir() { await borrar('/api/sesion'); location.href = '/'; }

// ---------------------------------------------------------------- formatos
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
const num = (v, d = 1) => (v == null ? '—' : Number(v).toLocaleString('es-CO', { maximumFractionDigits: d }));
const fecha = (iso) => (iso ? new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '—');
const hora = (iso) => (iso ? new Date(iso).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' }) : '—');
const legible = (t) => String(t ?? '').replaceAll('_', ' ');

const ESTADOS = {
  abierto: ['Abierto', 'primary'], rechazado: ['Rechazado', 'warning'], cerrado: ['Cerrado', 'success'],
  cerrado_faltante: ['Con faltante', 'warning'], sin_cierre: ['Sin cierre', 'danger'], anulado: ['Anulado', 'secondary'],
};
function chip(estado) {
  const [t, c] = ESTADOS[estado] || [legible(estado), 'secondary'];
  return `<span class="badge text-bg-${c}">${esc(t)}</span>`;
}

function aviso(texto, tipo = 'success', ms = 4500) {
  let caja = document.getElementById('avisos');
  if (!caja) { caja = document.createElement('div'); caja.id = 'avisos'; document.body.appendChild(caja); }
  const a = document.createElement('div');
  a.className = `alert alert-${tipo} shadow-sm mb-2`;
  a.innerHTML = texto;
  caja.appendChild(a);
  setTimeout(() => a.remove(), ms);
}

function descargarCSV(nombre, filas) {
  if (!filas.length) return aviso('No hay datos para exportar', 'warning');
  const columnas = Object.keys(filas[0]);
  const celda = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`;
  const texto = [columnas.join(';'), ...filas.map((f) => columnas.map((c) => celda(f[c])).join(';'))].join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['﻿' + texto], { type: 'text/csv;charset=utf-8' }));
  a.download = nombre;
  a.click();
}

// ---------------------------------------------------------------- mapas
function mapaBase(elemento, opciones = {}) {
  const m = L.map(elemento, opciones).setView(CALI, 12);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; OpenStreetMap',
  }).addTo(m);
  return m;
}

function capaNormativa(geojson) {
  return L.geoJSON(geojson, {
    style: (f) => (f.properties.capa === 'receptor'
      ? { color: '#1f7a4d', weight: 2, fillOpacity: 0.25 }
      : { color: '#b42318', weight: 1, fillOpacity: 0.3, dashArray: '4' }),
    onEachFeature: (f, capa) => {
      const p = f.properties;
      capa.bindPopup(p.capa === 'receptor'
        ? `<b>${esc(p.nombre)}</b><br>Receptor inscrito · ${esc(legible(p.tipo))}${p.pin_dagma ? `<br>PIN ${esc(p.pin_dagma)}` : ''}`
        : `<b>Zona prohibida</b> (Res. 0472, art. 20)<br>${esc(legible(p.tipo))}${p.nombre ? ' · ' + esc(p.nombre) : ''}`);
    },
  });
}

/* Capas WMS publicadas por GeoServer (solo si la plataforma tiene GeoServer configurado). */
async function capasWMS() {
  const c = await get('/api/publico/config');
  if (!c.wms) return {};
  const wms = (capa, extra = {}) => L.tileLayer.wms(c.wms, {
    layers: `rcd:${capa}`, format: 'image/png', transparent: true, version: '1.1.1',
    attribution: 'GeoServer · datos IDESC', ...extra });
  return {
    'Comunas (WMS · GeoServer)': wms('comunas'),
    'Barrios (WMS · GeoServer)': wms('barrios'),
    'Capa normativa (WMS · GeoServer)': wms('capa_normativa', { opacity: 0.85 }),
  };
}

function ubicacionDispositivo() {
  return new Promise((ok, mal) => {
    if (!navigator.geolocation) return mal(new Error('Este dispositivo no tiene GPS.'));
    navigator.geolocation.getCurrentPosition(
      (p) => ok({ lon: p.coords.longitude, lat: p.coords.latitude, precision: p.coords.accuracy }),
      () => mal(new Error('No se pudo obtener la ubicación. Revisa el permiso del GPS.')),
      { enableHighAccuracy: true, timeout: 10000 });
  });
}

/* Selector de ubicación: los 3 mecanismos de ingreso espacial (GPS · Dirección · Mapa). */
function selectorUbicacion(contenedor) {
  contenedor.innerHTML = `
    <div class="btn-group w-100 mb-2" role="group" aria-label="Cómo ubicar el punto">
      <button type="button" class="btn btn-outline-primary" data-modo="gps"><i class="bi bi-crosshair"></i> GPS</button>
      <button type="button" class="btn btn-outline-primary" data-modo="direccion"><i class="bi bi-signpost-2"></i> Dirección</button>
      <button type="button" class="btn btn-outline-primary" data-modo="mapa"><i class="bi bi-pin-map"></i> Mapa</button>
    </div>
    <div class="input-group mb-2 d-none" data-dir>
      <input class="form-control" placeholder="Calle 5 # 39-20" data-texto autocomplete="street-address">
      <button class="btn btn-primary" type="button" data-buscar>Buscar</button>
    </div>
    <div class="mapa-mini" data-mapa></div>
    <div class="small mt-1 text-secondary" data-estado>Elige cómo ubicar el punto.</div>`;
  const $ = (s) => contenedor.querySelector(s);
  const mapa = mapaBase($('[data-mapa]'));
  let marcador = null, modo = null, direccion = null, punto = null;

  const estado = (t, clase = 'text-secondary') => { const e = $('[data-estado]'); e.className = `small mt-1 ${clase}`; e.innerHTML = t; };
  const poner = (lat, lon, zoom = 17) => {
    punto = { lat, lon };
    if (!marcador) {
      marcador = L.marker([lat, lon], { draggable: true }).addTo(mapa);
      marcador.on('dragend', () => {
        const p = marcador.getLatLng();
        punto = { lat: p.lat, lon: p.lng };
        if (modo === 'gps') activar('mapa', false);
      });
    } else marcador.setLatLng([lat, lon]);
    mapa.setView([lat, lon], zoom);
  };
  async function usarGps() {
    estado('Buscando tu ubicación…');
    try {
      const p = await ubicacionDispositivo();
      poner(p.lat, p.lon);
      estado(`Ubicación del GPS (±${Math.round(p.precision)} m). Puedes arrastrar el pin.`, 'text-success');
    } catch (e) { estado(`${esc(e.message)} Usa la dirección o el mapa.`, 'text-danger'); }
  }
  async function buscar() {
    const q = $('[data-texto]').value.trim();
    if (!q) return;
    estado('Buscando la dirección…');
    try {
      const r = await get('/api/publico/geocodificar?q=' + encodeURIComponent(q));
      direccion = r.direccion_normalizada || q;
      poner(r.lat, r.lon);
      const detalle = `${esc(direccion)}${r.barrio ? ' · ' + esc(r.barrio) : ''} · confianza ${r.confianza ?? '—'}%`;
      if (r.verificar_en_mapa) estado(`${detalle}<br><b>Confianza baja: revisa el pin y arrástralo si hace falta.</b>`, 'text-warning-emphasis');
      else estado(detalle, 'text-success');
    } catch (e) { estado(esc(e.message), 'text-danger'); }
  }
  function activar(nuevo, accion = true) {
    modo = nuevo;
    contenedor.querySelectorAll('[data-modo]').forEach((b) => b.classList.toggle('active', b.dataset.modo === modo));
    $('[data-dir]').classList.toggle('d-none', modo !== 'direccion');
    if (!accion) return;
    if (modo === 'gps') usarGps();
    if (modo === 'mapa') estado('Toca el mapa en el lugar exacto.');
    if (modo === 'direccion') $('[data-texto]').focus();
  }
  contenedor.querySelectorAll('[data-modo]').forEach((b) => (b.onclick = () => activar(b.dataset.modo)));
  $('[data-buscar]').onclick = buscar;
  $('[data-texto]').onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); buscar(); } };
  mapa.on('click', (e) => {
    if (modo !== 'mapa') return;
    poner(e.latlng.lat, e.latlng.lng, Math.max(mapa.getZoom(), 16));
    estado('Punto marcado en el mapa.', 'text-success');
  });
  setTimeout(() => mapa.invalidateSize(), 250);

  return {
    mapa,
    refrescar: () => mapa.invalidateSize(),
    obtener() {
      if (!punto) throw new Error('Falta la ubicación: usa el GPS, una dirección o el mapa.');
      return { lon: punto.lon.toFixed(6), lat: punto.lat.toFixed(6), mecanismo: modo,
               direccion: modo === 'direccion' ? direccion || $('[data-texto]').value : '' };
    },
  };
}

/* Botones de opción (tipo de RCD, volumen…). Devuelve una función que lee el valor elegido. */
function chips(contenedor, opciones, inicial) {
  let valor = inicial;
  contenedor.innerHTML = opciones.map((o) =>
    `<button type="button" class="btn btn-outline-secondary me-1 mb-1 ${String(o.valor) === String(inicial) ? 'active' : ''}"
       data-v="${esc(o.valor)}">${esc(o.texto)}</button>`).join('');
  contenedor.onclick = (e) => {
    const b = e.target.closest('[data-v]');
    if (!b) return;
    valor = b.dataset.v;
    contenedor.querySelectorAll('[data-v]').forEach((x) => x.classList.toggle('active', x === b));
  };
  return () => valor;
}

const TIPO_CORTO = {
  EXC: 'Tierra / excavación', CIM: 'Cimentación', PET: 'Concreto, ladrillo', MET: 'Metal (chatarra)',
  MAD: 'Madera', VID: 'Vidrio', PLA: 'Plástico / drywall', NAP: 'Mezclado (no aprovechable)',
};
const opcionesTipo = (tipos) => tipos.map((t) => ({ valor: t.id, texto: TIPO_CORTO[t.codigo] || t.nombre }));

async function tiposRCD() {
  if (!tiposRCD.cache) tiposRCD.cache = (await get('/api/publico/tipos-rcd')).tipos;
  return tiposRCD.cache;
}
