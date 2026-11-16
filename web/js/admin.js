/* Administrador: pantallas P1–P6. */
const $ = (id) => document.getElementById(id);
const cargadas = {};
const graficos = {};
let tipos = [];

// ================================================================ pestañas
function abrirPestana(p) {
  document.querySelectorAll('#pestanas .nav-link').forEach((a) => a.classList.toggle('active', a.dataset.p === p));
  document.querySelectorAll('.pestana').forEach((s) => s.classList.toggle('d-none', s.id !== `p-${p}`));
  const iniciar = { dashboard, seguimiento, control, geocercas, movimientos, flota }[p];
  if (!cargadas[p]) cargadas[p] = iniciar();
  else if (cargadas[p].refrescar) cargadas[p].refrescar();
}
document.querySelectorAll('#pestanas .nav-link').forEach((a) => (a.onclick = (e) => {
  e.preventDefault(); history.replaceState(null, '', `#${a.dataset.p}`); abrirPestana(a.dataset.p);
}));

const tabla = (cabeza, filas) => `<table class="table tabla-compacta mb-0"><thead><tr>${cabeza.map((c) => `<th>${c}</th>`).join('')}</tr></thead>
  <tbody>${filas.join('') || `<tr><td colspan="${cabeza.length}" class="text-secondary">Sin datos</td></tr>`}</tbody></table>`;

// ================================================================ P1 DASHBOARD
function dashboard() {
  const hoy = new Date();
  $('r-anio').value = hoy.getFullYear();
  $('r-trim').value = Math.floor(hoy.getMonth() / 3) + 1;
  $('b-reporte').onclick = async () => {
    const r = await get(`/api/admin/reporte-trimestral?anio=${$('r-anio').value}&trimestre=${$('r-trim').value}`);
    descargarCSV(`reporte_rcd_${r.anio}_T${r.trimestre}.csv`, r.filas);
  };
  async function cargar() {
    const d = await get('/api/admin/dashboard');
    const m = d.meta, k = d.indicadores;
    $('k-pct').textContent = m.porcentaje == null ? '—' : `${num(m.porcentaje)}%`;
    $('k-meta').textContent = `de ${num(m.meta_pct, 0)}% exigido`;
    $('k-barra').style.width = `${Math.min(100, m.porcentaje || 0)}%`;
    $('k-barra').className = `progress-bar ${m.porcentaje >= m.meta_pct ? 'bg-success' : 'bg-warning'}`;
    $('k-falta').innerHTML = m.falta_t > 0
      ? `Faltan <b>${num(m.falta_t)} t</b> aprovechadas para cumplir (de ${num(m.generado_t)} t generadas)`
      : `<span class="text-success">Meta cumplida</span> · ${num(m.aprovechado_t)} de ${num(m.generado_t)} t`;
    $('k-recibidos').textContent = num(k.m3_recibidos);
    $('k-curso').textContent = k.en_curso;
    $('k-alertas').textContent = k.alertas_abiertas;
    $('k-altas').textContent = k.alertas_altas ? `${k.alertas_altas} de gravedad alta` : '';
    $('k-arrojos').textContent = k.arrojos_mes;
    $('n-alertas').textContent = k.alertas_abiertas || '';

    // tendencia semanal por tipo (barras apiladas)
    const semanas = [...new Set(d.tendencia_por_tipo.map((t) => t.semana))];
    const nombres = [...new Set(d.tendencia_por_tipo.map((t) => t.tipo_rcd))];
    const paleta = ['#1f7a4d', '#1f6f8b', '#6b8e23', '#8e44ad', '#b26a00', '#2c3e50', '#16a085', '#b42318'];
    graficos.tendencia?.destroy();
    graficos.tendencia = new Chart($('g-tendencia'), {
      type: 'bar',
      data: { labels: semanas.map((s) => `Sem. ${new Date(s + 'T00:00').toLocaleDateString('es-CO', { day: '2-digit', month: 'short' })}`),
              datasets: nombres.map((n, i) => ({ label: n.split(':')[0], backgroundColor: paleta[i % paleta.length],
                data: semanas.map((s) => d.tendencia_por_tipo.filter((t) => t.semana === s && t.tipo_rcd === n).reduce((a, t) => a + t.m3, 0)) })) },
      options: { scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'm³' } } } },
    });
    graficos.estados?.destroy();
    graficos.estados = new Chart($('g-estados'), {
      type: 'doughnut',
      data: { labels: d.estados.map((e) => (ESTADOS[e.estado] || [e.estado])[0]),
              datasets: [{ data: d.estados.map((e) => e.n),
                           backgroundColor: d.estados.map((e) => ({ abierto: '#1f6f8b', rechazado: '#e0a100', cerrado: '#1f7a4d',
                             cerrado_faltante: '#f0b429', sin_cierre: '#b42318', anulado: '#999' }[e.estado])) }] },
      options: { plugins: { legend: { position: 'bottom' } } },
    });
    $('t-obras').innerHTML = tabla(['Obra', 'Generado', 'Aprovechado', 'Faltan'], m.por_obra.map((o) => `<tr>
      <td>${esc(o.obra)}</td><td>${num(o.generado_t)} t</td>
      <td style="min-width:140px"><div class="progress"><div class="progress-bar ${o.porcentaje >= o.meta_pct ? 'bg-success' : 'bg-warning'}"
        style="width:${o.porcentaje || 0}%">${num(o.porcentaje, 0)}%</div></div></td><td>${num(o.falta_t)} t</td></tr>`));
    $('t-operarios').innerHTML = tabla(['Operario', 'Perfil', 'Movim.', 'Entradas', 'Arrojos'], d.operarios_activos.map((o) =>
      `<tr><td>${esc(o.nombre)}</td><td>${esc(o.perfil)}</td><td>${o.movimientos}</td><td>${o.entradas}</td><td>${o.arrojos}</td></tr>`));
    $('t-balance').innerHTML = tabla(['Receptor', 'Entra', 'Sale'], d.balance_receptores.map((b) =>
      `<tr><td>${esc(b.nombre)}</td><td>${num(b.entradas_m3)}</td><td>${num(b.salidas_m3)}</td></tr>`));
  }
  cargar();
  return { refrescar: cargar };
}

// ================================================================ P2 SEGUIMIENTO
function seguimiento() {
  const mapa = mapaBase('s-mapa');
  const recorrido = L.layerGroup().addTo(mapa);
  get('/api/mapas/normativa').then((g) => capaNormativa(g).addTo(mapa));
  const marcadores = L.layerGroup().addTo(mapa);
  let vehiculos = [];
  const SENSOR = { motor_encendido: 'Motor encendido · cámara activa', motor_apagado: 'Motor apagado',
                   compuerta_abierta: 'Compuerta abierta', compuerta_cerrada: 'Compuerta cerrada', movimiento_carga: 'Movimiento en la carga' };

  async function elegir(placa) {
    const v = vehiculos.find((x) => x.placa === placa);
    document.querySelectorAll('#s-lista .tarjeta').forEach((t) => t.classList.toggle('border-primary', t.dataset.placa === placa));
    $('s-placa').textContent = placa;
    const alerta = (v.sensores || []).some((s) => s.tipo === 'compuerta_abierta' || s.tipo === 'movimiento_carga');
    $('s-camara').innerHTML = alerta
      ? '<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> Apertura detectada en tránsito</span><br><span class="small">Grabación disponible para revisión</span>'
      : 'Interior de la volqueta · sin novedad';
    $('s-eventos').innerHTML = [
      `<li><b>${fecha(v.abierto_en)}</b> Movimiento ${esc(v.codigo)} abierto${v.obra ? ' en ' + esc(v.obra) : ''}</li>`,
      ...(v.sensores || []).map((s) => `<li class="${s.tipo === 'compuerta_abierta' || s.tipo === 'movimiento_carga' ? 'mal' : ''}">
        <b>${hora(s.hora)}</b> ${esc(SENSOR[s.tipo] || s.tipo)}</li>`),
      `<li class="medio">Llegada a destino: pendiente</li>`].join('');
    recorrido.clearLayers();
    const g = await get(`/api/mapas/recorrido/${encodeURIComponent(placa)}?horas=12`);
    const capa = L.geoJSON(g, {
      style: { color: '#1f6f8b', weight: 4 },
      pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 9, color: '#fff', weight: 2, fillOpacity: 0.95,
        fillColor: f.properties.zona_prohibida ? '#b42318' : '#e0a100' }),
      onEachFeature: (f, l) => f.properties.tipo === 'parada' && l.bindPopup(`<b>Parada de ${num(f.properties.minutos, 0)} min</b>
        ${f.properties.zona_prohibida ? `<br><span class="text-danger">En zona prohibida: ${esc(legible(f.properties.zona_prohibida))}</span>` : ''}`),
    }).addTo(recorrido);
    if (g.features.length) mapa.fitBounds(capa.getBounds().pad(0.3));
    else if (v.lat) mapa.setView([v.lat, v.lon], 15);
  }
  async function cargar() {
    vehiculos = (await get('/api/admin/seguimiento')).vehiculos;
    marcadores.clearLayers();
    $('s-lista').innerHTML = vehiculos.map((v) => `
      <div class="tarjeta py-2" role="button" data-placa="${esc(v.placa)}">
        <div class="d-flex justify-content-between"><b>${esc(v.placa)}</b>
          ${v.alertas ? `<span class="badge text-bg-danger">${v.alertas} alerta(s)</span>` : '<span class="badge text-bg-success">En ruta</span>'}</div>
        <div class="small text-secondary">${esc(v.codigo)} · ${esc(v.obra || 'Particular')}<br>Última posición: ${hora(v.ultima_posicion_en)}</div>
      </div>`).join('') || '<div class="text-secondary small">No hay vehículos de la empresa en tránsito.</div>';
    vehiculos.filter((v) => v.lat).forEach((v) => L.marker([v.lat, v.lon]).bindTooltip(v.placa, { permanent: true }).addTo(marcadores));
    $('s-lista').onclick = (e) => { const t = e.target.closest('[data-placa]'); if (t) elegir(t.dataset.placa); };
    if (vehiculos.length) elegir(vehiculos[0].placa);
  }
  setTimeout(() => mapa.invalidateSize(), 50);
  cargar();
  return { refrescar: () => { mapa.invalidateSize(); cargar(); } };
}

// ================================================================ P3 CONTROL
function control() {
  const mapa = mapaBase('c-mapa');
  const capas = {};
  const TITULO = { sin_cierre: 'Sin cierre', faltante: 'Faltante', rechazo: 'Rechazo', zona_prohibida: 'Parada en zona prohibida',
    parada_sospechosa: 'Parada sospechosa', compuerta_en_transito: 'Compuerta abierta en tránsito',
    cierre_fuera_geocerca: 'Cierre fuera de geocerca', arrojo_cercano: 'Arrojo con movimientos cerca' };

  async function cargarCapas() {
    const [norma, flujos, movs, dens, arrojos] = await Promise.all(['normativa', 'flujos', 'movimientos', 'densidad', 'arrojos']
      .map((c) => get(`/api/mapas/${c}`)));
    const maxM3 = Math.max(1, ...flujos.features.map((f) => f.properties.m3));
    capas['Flujos obra → receptor'] = L.geoJSON(flujos, {
      style: (f) => ({ color: f.properties.estado === 'cerrado_faltante' ? '#e0a100' : '#1f6f8b',
                       weight: 2 + 8 * (f.properties.m3 / maxM3), opacity: 0.8 }),
      onEachFeature: (f, l) => l.bindPopup(`<b>${esc(f.properties.codigo)}</b> ${chip(f.properties.estado)}<br>${num(f.properties.m3)} m³ → ${esc(f.properties.receptor)}`),
    });
    const cluster = L.markerClusterGroup();
    movs.features.forEach((f) => cluster.addLayer(L.marker([f.geometry.coordinates[1], f.geometry.coordinates[0]])
      .bindPopup(`<b>${esc(f.properties.codigo)}</b> ${chip(f.properties.estado)}<br>${num(f.properties.m3)} m³`)));
    capas['Clúster de movimientos'] = cluster;
    const maxCelda = Math.max(1, ...dens.features.map((f) => f.properties.m3));
    capas['Densidad (m³ por celda de 500 m)'] = L.geoJSON(dens, {
      style: (f) => ({ color: '#8e1b10', weight: 0.5, fillColor: '#b42318', fillOpacity: 0.15 + 0.6 * (f.properties.m3 / maxCelda) }),
      onEachFeature: (f, l) => l.bindPopup(`${f.properties.movimientos} movimientos · ${num(f.properties.m3)} m³`),
    });
    capas['Arrojos reportados'] = L.geoJSON(arrojos, {
      pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 7, color: '#b42318', fillColor: '#b42318', fillOpacity: 0.7 }),
      onEachFeature: (f, l) => l.bindPopup(`<b>Arrojo</b> · ${fecha(f.properties.reportado_en)}<br>Movimientos sin cerrar cerca: ${f.properties.movimientos_cercanos}`),
    });
    capas['Receptores y zonas prohibidas'] = capaNormativa(norma);
    capas['Flujos obra → receptor'].addTo(mapa);
    capas['Receptores y zonas prohibidas'].addTo(mapa);
    capas['Arrojos reportados'].addTo(mapa);
    Object.assign(capas, await capasWMS());          // comunas, barrios y capa normativa por WMS (GeoServer)
    L.control.layers(null, capas, { collapsed: false }).addTo(mapa);
    if (flujos.features.length) mapa.fitBounds(capas['Flujos obra → receptor'].getBounds().pad(0.3));
  }
  async function cargarAlertas() {
    const { alertas } = await get(`/api/admin/alertas?estado=${$('c-filtro').value}`);
    $('c-alertas').innerHTML = alertas.map((a) => `
      <div class="tarjeta py-2 alerta-item ${a.gravedad}" data-lat="${a.lat ?? ''}" data-lon="${a.lon ?? ''}" role="button">
        <div class="d-flex justify-content-between"><b>${esc(TITULO[a.tipo] || a.tipo)}</b><span class="small">${hora(a.creada_en)}</span></div>
        <div class="small text-secondary">${a.codigo ? esc(a.codigo) + ' · ' : ''}${a.placa ? esc(a.placa) : ''}
          ${a.detalle?.zona_prohibida ? ' · ' + esc(legible(a.detalle.zona_prohibida)) : ''}
          ${a.detalle?.faltante_m3 ? ` · faltan ${num(a.detalle.faltante_m3)} m³` : ''}${a.detalle?.motivo ? ' · ' + esc(legible(a.detalle.motivo)) : ''}</div>
        ${a.estado === 'abierta' ? `<div class="mt-1"><button class="btn btn-sm btn-outline-success" data-alerta="${a.id}" data-estado="revisada">Revisada</button>
          <button class="btn btn-sm btn-outline-danger" data-alerta="${a.id}" data-estado="escalada">Escalar</button></div>`
          : `<span class="badge text-bg-secondary">${esc(a.estado)}</span>`}
      </div>`).join('') || '<div class="text-secondary small">No hay alertas.</div>';
  }
  $('c-alertas').onclick = async (e) => {
    const b = e.target.closest('[data-alerta]');
    if (b) { await patch(`/api/admin/alertas/${b.dataset.alerta}`, { estado: b.dataset.estado }); aviso('Alerta actualizada'); cargarAlertas(); return; }
    const t = e.target.closest('[data-lat]');
    if (t && t.dataset.lat) mapa.flyTo([t.dataset.lat, t.dataset.lon], 16);
  };
  $('c-filtro').onchange = cargarAlertas;
  setTimeout(() => mapa.invalidateSize(), 50);
  cargarCapas(); cargarAlertas();
  return { refrescar: () => { mapa.invalidateSize(); cargarAlertas(); } };
}

// ================================================================ P4 GEOCERCAS
function geocercas() {
  const mapa = mapaBase('g-mapa');
  const normativa = L.layerGroup().addTo(mapa);
  const dibujo = new L.FeatureGroup().addTo(mapa);
  let geometria = null;
  mapa.addControl(new L.Control.Draw({
    draw: { polygon: { allowIntersection: false }, polyline: true, rectangle: false, circle: false, marker: false, circlemarker: false },
    edit: { featureGroup: dibujo, edit: false, remove: false },
  }));
  $('g-acepta').innerHTML = tipos.map((t) => `<label class="me-2"><input type="checkbox" value="${esc(t.codigo)}" ${t.categoria === 'aprovechable' ? 'checked' : ''}>
    ${esc(TIPO_CORTO[t.codigo] || t.codigo)}</label>`).join('');
  const esZona = () => $('g-zona').checked;
  $('g-receptor').onchange = $('g-zona').onchange = () => {
    $('g-campos-receptor').classList.toggle('d-none', esZona());
    $('g-campos-zona').classList.toggle('d-none', !esZona());
  };
  mapa.on(L.Draw.Event.CREATED, (e) => {
    dibujo.clearLayers();
    let gj = e.layer.toGeoJSON();
    if (gj.geometry.type === 'LineString') {          // río o canal: franja con Turf.js
      $('g-zona').checked = true; $('g-zona').onchange();
      gj = turf.buffer(gj, Number($('g-franja').value || 30), { units: 'meters' });
    }
    geometria = gj.geometry;
    L.geoJSON(gj, { style: { color: '#1f6f8b', dashArray: '5', fillOpacity: 0.2 } }).addTo(dibujo);
    $('g-form').classList.remove('d-none');
    const area = turf.area(gj);
    aviso(`Geometría lista: ${num(area / 10000, 2)} ha`, 'info');
  });
  $('g-guardar').onclick = async () => {
    try {
      if (esZona()) {
        await post('/api/admin/zonas-prohibidas', { tipo: $('g-tipo-zona').value, nombre: $('g-zona-nombre').value,
          franja_m: $('g-franja').value, geometria });
      } else {
        await post('/api/admin/receptores', { nombre: $('g-nombre').value, tipo: $('g-tipo-receptor').value, pin_dagma: $('g-pin').value,
          geometria, acepta: [...document.querySelectorAll('#g-acepta input:checked')].map((i) => i.value) });
      }
      aviso('Guardado en la capa normativa');
      dibujo.clearLayers(); geometria = null; $('g-form').classList.add('d-none');
      cargar();
    } catch (err) { aviso(esc(err.message), 'danger'); }
  };
  async function cargar() {
    const [norma, { receptores }] = await Promise.all([get('/api/mapas/normativa'), get('/api/admin/receptores')]);
    normativa.clearLayers(); capaNormativa(norma).addTo(normativa);
    $('g-receptores').innerHTML = tabla(['Nombre', 'Tipo', ''], receptores.map((r) => `<tr class="${r.activo ? '' : 'text-secondary'}">
      <td>${esc(r.nombre)}</td><td>${esc(legible(r.tipo))}</td>
      <td>${r.activo ? `<button class="btn btn-sm btn-link text-danger p-0" data-desactivar="${r.id}">Desactivar</button>` : 'inactivo'}</td></tr>`));
    const zonas = norma.features.filter((f) => f.properties.capa === 'prohibida');
    const porTipo = {};
    zonas.forEach((z) => (porTipo[z.properties.tipo] = (porTipo[z.properties.tipo] || 0) + 1));
    const resumen = Object.entries(porTipo).sort((a, b) => b[1] - a[1])
      .map(([t, n]) => `<span class="badge text-bg-light border me-1 mb-1">${esc(legible(t))}: ${num(n, 0)}</span>`).join('');
    const ultimas = zonas.sort((a, b) => b.properties.id - a.properties.id).slice(0, 30);   // las más recientes primero
    $('g-zonas').innerHTML = `<div class="mb-2">${resumen}</div>
      <div class="small text-secondary mb-1">${num(zonas.length, 0)} zonas (IDESC + dibujadas). Se muestran las 30 más recientes.</div>` +
      tabla(['Zona', ''], ultimas.map((z) => `<tr><td>${esc(legible(z.properties.tipo))} · ${esc(z.properties.nombre || '')}</td>
      <td><button class="btn btn-sm btn-link text-danger p-0" data-eliminar="${z.properties.id}">Eliminar</button></td></tr>`));
  }
  document.querySelector('#p-geocercas .panel-lateral').onclick = async (e) => {
    const d = e.target.closest('[data-desactivar]'), z = e.target.closest('[data-eliminar]');
    if (d && confirm('¿Desactivar este receptor? Sus entradas históricas se conservan.')) { await borrar(`/api/admin/receptores/${d.dataset.desactivar}`); cargar(); }
    if (z && confirm('¿Eliminar esta zona prohibida de la capa normativa?')) { await borrar(`/api/admin/zonas-prohibidas/${z.dataset.eliminar}`); cargar(); }
  };
  setTimeout(() => mapa.invalidateSize(), 50);
  cargar();
  return { refrescar: () => mapa.invalidateSize() };
}

// ================================================================ P5 MOVIMIENTOS
function movimientos() {
  let filas = [];
  const modal = new bootstrap.Modal($('modal-ubicacion'));
  let mapaU = null, pin = null, codigoU = null;

  async function cargar() {
    const q = new URLSearchParams({ estado: $('m-estado').value, placa: $('m-placa').value, desde: $('m-desde').value, hasta: $('m-hasta').value });
    filas = (await get('/api/movimientos?' + q)).movimientos;
    $('m-tabla').innerHTML = filas.map((m) => `<tr>
      <td><a href="/m/${esc(m.codigo)}" target="_blank">${esc(m.codigo)}</a></td><td>${chip(m.estado)}${m.con_agravante ? ' <span class="badge text-bg-danger">agravante</span>' : ''}</td>
      <td>${esc(m.placa)}</td><td>${esc(m.obra || 'Particular')}</td><td>${esc(m.tipo_rcd.split(':')[0])}</td>
      <td class="text-end">${num(m.volumen_declarado_m3)}</td><td>${fecha(m.abierto_en)}</td><td>${esc(m.receptor || '—')}</td>
      <td class="text-nowrap">${['abierto', 'rechazado', 'sin_cierre'].includes(m.estado) ? `
        <button class="btn btn-sm btn-outline-primary" data-corregir="${esc(m.codigo)}" data-lat="${m.lat}" data-lon="${m.lon}" title="Corregir ubicación"><i class="bi bi-pin-map"></i></button>
        <button class="btn btn-sm btn-outline-danger" data-anular="${esc(m.codigo)}" title="Anular"><i class="bi bi-x-circle"></i></button>` : ''}</td></tr>`).join('')
      || '<tr><td colspan="9" class="text-secondary">No hay movimientos con esos filtros.</td></tr>';
  }
  $('m-tabla').onclick = async (e) => {
    const a = e.target.closest('[data-anular]'), c = e.target.closest('[data-corregir]');
    try {
      if (a && confirm(`¿Anular ${a.dataset.anular}? Dejará de contar, pero no se borra.`)) {
        await post(`/api/admin/movimientos/${a.dataset.anular}/anular`); aviso('Movimiento anulado'); cargar();
      }
    } catch (err) { aviso(esc(err.message), 'danger'); }
    if (c) {
      codigoU = c.dataset.corregir; $('u-codigo').textContent = codigoU;
      modal.show();
      setTimeout(() => {
        if (!mapaU) mapaU = mapaBase('u-mapa');
        mapaU.invalidateSize();
        const ll = [Number(c.dataset.lat), Number(c.dataset.lon)];
        if (pin) pin.setLatLng(ll); else pin = L.marker(ll, { draggable: true }).addTo(mapaU);
        mapaU.setView(ll, 17);
      }, 300);
    }
  };
  $('u-guardar').onclick = async () => {
    try {
      const p = pin.getLatLng();
      const r = await patch(`/api/admin/movimientos/${codigoU}/ubicacion`, { lon: p.lng, lat: p.lat });
      aviso(`Ubicación corregida (${num(r.detalle.desplazamiento_m, 0)} m). Quedó auditado.`);
      modal.hide(); cargar();
    } catch (err) { aviso(esc(err.message), 'danger'); }
  };
  $('m-anular-rango').onclick = async () => {
    const desde = prompt('Anular movimientos ABIERTOS de tu empresa desde (AAAA-MM-DD):');
    const hasta = desde && prompt('hasta (AAAA-MM-DD):');
    if (!desde || !hasta) return;
    try { const r = await post('/api/admin/movimientos/anular-rango', { desde, hasta }); aviso(`${r.anulados} movimiento(s) anulados`); cargar(); }
    catch (err) { aviso(esc(err.message), 'danger'); }
  };
  $('m-filtrar').onclick = cargar;
  $('m-csv').onclick = () => descargarCSV('movimientos.csv', filas);
  cargar();
  return { refrescar: cargar };
}

// ================================================================ P6 FLOTA Y USUARIOS
function flota() {
  async function cargar() {
    const f = await get('/api/admin/flota');
    $('f-vehiculos').innerHTML = tabla(['Placa', 'Tipo', 'm³', 'GPS', 'Cámara', 'Conductor'], f.vehiculos.map((v) => `<tr>
      <td><b>${esc(v.placa)}</b></td><td>${esc(v.tipo || '—')}</td><td>${num(v.capacidad_m3)}</td>
      <td>${v.tiene_gps ? '✓' : '—'}</td><td>${v.tiene_camara ? '✓' : '—'}</td><td>${esc(v.transportador || '—')}</td></tr>`));
    $('f-usuarios').innerHTML = tabla(['Nombre', 'Correo', 'Rol'], f.usuarios.map((u) =>
      `<tr><td>${esc(u.nombre)}</td><td>${esc(u.email)}</td><td>${esc(u.perfil || u.rol)}</td></tr>`));
  }
  $('f-nuevo-vehiculo').onsubmit = async (e) => {
    e.preventDefault();
    try {
      await post('/api/admin/vehiculos', { placa: $('v-placa').value, capacidad_m3: $('v-capacidad').value,
        tiene_gps: $('v-gps').checked, tiene_camara: $('v-camara').checked });
      e.target.reset(); aviso('Vehículo agregado'); cargar();
    } catch (err) { aviso(esc(err.message), 'danger'); }
  };
  $('f-nuevo-usuario').onsubmit = async (e) => {
    e.preventDefault();
    const perfil = $('u-perfil').value;
    try {
      await post('/api/admin/usuarios', { nombre: $('u-nombre').value, email: $('u-email').value, clave: $('u-clave').value,
        rol: perfil ? 'usuario' : 'admin', perfil: perfil || null });
      e.target.reset(); aviso('Usuario creado'); cargar();
    } catch (err) { aviso(esc(err.message), 'danger'); }
  };
  cargar();
  return { refrescar: cargar };
}

// ================================================================ inicio
(async () => {
  await sesion((u) => u.rol === 'admin');
  tipos = await tiposRCD();
  abrirPestana((location.hash || '#dashboard').slice(1));
  window.addEventListener('hashchange', () => abrirPestana((location.hash || '#dashboard').slice(1)));
})();
