/* econfig probe - paste into the DevTools console of an open e-config Cloud tab.
 *
 * Read-only. It makes no network calls and sends nothing anywhere:
 *   - checks that an auth token exists (never prints it)
 *   - borrows the page's own webpack require to reach IBM's CFR codec
 *   - dumps whatever product catalogs the app has already cached in IndexedDB
 *
 * The catalog cache is populated by simply opening a configuration in e-config,
 * so if a model is missing here, open it once in the UI and re-run.
 *
 * Results are left on window.__ecfg for inspection, and
 * __ecfg.save() downloads them as JSON.
 */
(async () => {
  const out = { at: new Date().toISOString(), origin: location.origin };
  const log = (...a) => console.log('%c[ecfg]', 'color:#0f62fe;font-weight:600', ...a);
  const bad = (...a) => console.log('%c[ecfg]', 'color:#b42318;font-weight:600', ...a);

  /* ---- 1. auth token ------------------------------------------------- */
  const raw = localStorage.getItem('ngMPL_jwToken');
  if (!raw) {
    bad('no ngMPL_jwToken in localStorage - are you logged in to e-config in this tab?');
    out.token = { present: false };
  } else {
    let claims = null;
    try {
      claims = JSON.parse(atob(raw.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch { /* opaque token */ }
    const exp = claims?.exp ? new Date(claims.exp * 1000) : null;
    out.token = {
      present: true,
      length: raw.length,
      expires: exp?.toISOString() ?? null,
      expired: exp ? exp < new Date() : null,
      // identity/entitlement claims only - never the token itself
      country: claims?.sub?.country ?? null,
      type: claims?.sub?.type ?? null,
      roles: claims?.sub?.roles ?? null,
      ceIds: claims?.sub?.bp_ceIds ?? null,
      geoAccess: claims?.sub?.geoAccess ?? null,
    };
    log('token present.', exp ? `expires ${exp.toLocaleString()}` : 'no exp claim',
        out.token.expired ? '(EXPIRED - reload the page)' : '');
    log('  roles:', out.token.roles, '| country:', out.token.country, '| CE ids:', out.token.ceIds);
  }

  /* ---- 2. the page's own webpack require + CFR codec ------------------ */
  try {
    const chunks = window.webpackChunkecfgcloud_app_frontend;
    if (!Array.isArray(chunks) && typeof chunks?.push !== 'function') throw new Error('chunk array not found');
    let req = null;
    // A chunk id the runtime has not installed makes it run our callback with
    // its __webpack_require__, which is the whole point of this push.
    chunks.push([[`probe_${Date.now()}`], {}, (r) => { req = r; }]);
    if (!req) throw new Error('runtime did not hand back a require');
    window.__ecfgRequire = req;
    const codec = req(3294);
    out.codec = {
      ok: !!(codec?.gQ?.fromCFRSync && codec?.oD?.fromCFRJSON),
      decode: Object.keys(codec?.gQ ?? {}),
      encode: Object.keys(codec?.oD ?? {}),
    };
    window.__ecfgCodec = codec;
    log('codec reachable in-page.  decode:', out.codec.decode.join(', '));
  } catch (e) {
    bad('codec not reachable:', e.message);
    out.codec = { ok: false, error: e.message };
  }

  /* ---- 3. cached product catalogs ------------------------------------ */
  const readStore = (dbName, storeName) =>
    new Promise((resolve) => {
      const open = indexedDB.open(dbName);
      open.onerror = () => resolve(null);
      open.onsuccess = () => {
        const db = open.result;
        if (!db.objectStoreNames.contains(storeName)) return resolve(null);
        const tx = db.transaction(storeName, 'readonly').objectStore(storeName);
        const keys = tx.getAllKeys();
        keys.onsuccess = () => {
          const values = tx.getAll();
          values.onsuccess = () => resolve({ keys: keys.result, values: values.result });
          values.onerror = () => resolve({ keys: keys.result, values: [] });
        };
        keys.onerror = () => resolve(null);
      };
    });

  const dbs = (await indexedDB.databases?.()) ?? [];
  out.databases = dbs.map((d) => d.name);
  log('IndexedDB databases:', out.databases.join(', ') || '(none)');

  // Only open a database that already exists - opening an unknown name would
  // create an empty one as a side effect.
  const dbName = out.databases.find((n) => /productscatalog/i.test(n ?? ''));
  const cat = dbName ? await readStore(dbName, 'products') : null;
  if (!dbName) bad('no ProductsCatalog database in this origin.');
  if (!cat || !cat.keys.length) {
    bad('no cached catalogs. Open a configuration in e-config once, then re-run this probe.');
    out.catalogs = [];
  } else {
    // key format: PRODUCTBASE_region_country_beoptdate_model_type
    out.catalogs = cat.keys.map((k, i) => {
      let parsed = cat.values[i];
      if (typeof parsed === 'string') { try { parsed = JSON.parse(parsed); } catch {} }
      const entries = Array.isArray(parsed) ? parsed : parsed?.catalog ?? [];
      const categories = {};
      let features = 0;
      for (const e of entries) {
        categories[e.category ?? '(none)'] = (categories[e.category ?? '(none)'] ?? 0) + 1;
        features += e.features?.length ?? 0;
      }
      return { key: k, products: entries.length, features, categories, sample: entries[0] ?? null };
    });

    console.table(out.catalogs.map((c) => ({
      key: c.key, products: c.products, features: c.features,
      categories: Object.keys(c.categories).join(', '),
    })));
    const first = out.catalogs.find((c) => c.sample);
    if (first) {
      log('sample catalog entry (shape matters most - field names, category, features[]):');
      console.dir(first.sample, { depth: 4 });
    }
    window.__ecfgCatalogRaw = cat;
  }

  /* ---- 4. export ------------------------------------------------------ */
  out.save = () => {
    const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `econfig-probe-${Date.now()}.json`;
    a.click();
  };
  out.saveCatalogs = () => {
    const blob = new Blob([JSON.stringify(window.__ecfgCatalogRaw ?? {}, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `econfig-catalogs-${Date.now()}.json`;
    a.click();
  };

  window.__ecfg = out;
  log('done. window.__ecfg holds the report.');
  log('  __ecfg.save()          -> download the report (no token, safe to share)');
  log('  __ecfg.saveCatalogs()  -> download the full catalog cache (large)');
  return out;
})();
